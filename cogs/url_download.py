# cogs/url_download.py

import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import aiohttp
import os
import time
import asyncio
import math
import re
from typing import Optional

# ---------- CONFIG ----------
# Your FastAPI base (no trailing slash)
EXTERNAL_HOST = "https://fadi-s-assistant-production.up.railway.app"
MAX_DISCORD_FILESIZE = 8 * 1024 * 1024  # 8MB
DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
# ----------------------------


def sizeof_fmt(num, suffix="B"):
    """Convert bytes → human-readable format."""
    for unit in ["", "K", "M", "G"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}T{suffix}"


def sanitize_filename(name: str, default: str = "video") -> str:
    """
    Remove emojis and unsafe characters; return ASCII-ish safe name.
    Keep letters, numbers, space, dot, dash, underscore; collapse spaces.
    """
    # strip all non-allowed chars
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", name)
    # collapse whitespace to single space, then to underscores
    cleaned = re.sub(r"\s+", " ", cleaned).strip().replace(" ", "_")
    # avoid leading dots and empty names
    cleaned = cleaned.lstrip(".")
    if not cleaned:
        cleaned = default
    # limit length a bit to avoid OS/path issues
    return cleaned[:120]


async def upload_external(file_path: str) -> Optional[str]:
    """Upload file to external hosting and return a direct *download* link."""
    upload_url = f"{EXTERNAL_HOST}/upload"
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            form = aiohttp.FormData()
            # send with our sanitized basename
            form.add_field("file", f, filename=os.path.basename(file_path))
            async with session.post(upload_url, data=form) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    # the API should return a full URL to /download/{file}; normalize if needed
                    url = res.get("file_url")
                    if not url:
                        return None
                    # if it's relative, prefix our host
                    if not url.startswith("http"):
                        url = f"{EXTERNAL_HOST.rstrip('/')}{url}"
                    # ensure we give users an auto-download endpoint
                    url = url.replace("/files/", "/download/")
                    return url
                return None


class ProgressHook:
    """Thread-safe progress updates using bot loop + a clean progress bar."""
    def __init__(self, message: discord.Message, loop: asyncio.AbstractEventLoop):
        self.message = message
        self.loop = loop
        self.last_update = 0.0
        self.final_path: Optional[str] = None

    def _pct(self, d) -> Optional[float]:
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes")
        if total and downloaded is not None:
            return max(0.0, min(100.0, (downloaded / total) * 100.0))
        # fallback to yt-dlp provided string
        s = (d.get("_percent_str") or "").strip().replace("%", "")
        try:
            return float(s)
        except Exception:
            return None

    def hook(self, d):
        status = d.get("status")
        now = time.time()

        if status == "downloading":
            pct = self._pct(d)
            if pct is None:
                return

            # 10-block bar
            blocks = int(pct // 10)
            bar = "▰" * blocks + "▱" * (10 - blocks)

            speed = (d.get("_speed_str") or "").strip()
            eta = d.get("eta")
            eta_str = f"{int(eta)}s" if isinstance(eta, (int, float)) else "—"

            if now - self.last_update >= 1.0:
                self.last_update = now
                txt = f"⬇️ Downloading… {pct:.1f}%\n{bar}\nSpeed: {speed} • ETA: {eta_str}"
                asyncio.run_coroutine_threadsafe(self.message.edit(content=txt), self.loop)

        elif status == "finished":
            # yt-dlp gives us the final path after merge
            fn = d.get("filename")
            if isinstance(fn, str):
                self.final_path = fn
            asyncio.run_coroutine_threadsafe(self.message.edit(content="📦 Merging & Finalizing…"), self.loop)


class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _handle_download(self, carrier, url: str, is_slash: bool):
        start_time = time.time()

        # initial status message
        if is_slash:
            await carrier.response.defer(thinking=True)
            status_msg = await carrier.followup.send("🔄 Fetching video info…", wait=True)
        else:
            status_msg = await carrier.reply("🔄 Fetching video info…")

        # Force best quality and merge to MP4. Use %(id)s to avoid weird titles mid-download.
        outtmpl = os.path.join(DOWNLOADS_DIR, "%(id)s.%(ext)s")
        ydl_opts = {
            "format": "bv*+ba/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "concurrent_fragment_downloads": 3,
        }

        info = None
        filename_guess = None
        try:
            # probe
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                media_id = info.get("id", "video")
                duration = info.get("duration", 0)
                duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))
                # best guess before merge
                filename_guess = os.path.join(DOWNLOADS_DIR, f"{media_id}.{info.get('ext', 'mp4')}")

            # progress hook (thread-safe)
            progress = ProgressHook(status_msg, self.bot.loop)
            ydl_opts["progress_hooks"] = [progress.hook]

            # show initial bar
            await status_msg.edit(content="⬇️ Downloading… 0.0%\n▱▱▱▱▱▱▱▱▱▱\nSpeed: — • ETA: —")

            # run blocking download in a worker thread
            def _run():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            await asyncio.to_thread(_run)

            # determine final path (after merge to mp4)
            final_path = progress.final_path
            if not final_path or not os.path.exists(final_path):
                # try common fallbacks
                cand1 = os.path.join(DOWNLOADS_DIR, f"{info['id']}.mp4")
                cand2 = filename_guess.replace(f".{info.get('ext','mp4')}", ".mp4")
                cand3 = filename_guess
                for c in (cand1, cand2, cand3):
                    if c and os.path.exists(c):
                        final_path = c
                        break

            if not final_path or not os.path.exists(final_path):
                raise FileNotFoundError(f"Final file not found (id={info.get('id')})")

            # rename to a clean, friendly mp4 filename (no emojis)
            safe_name = sanitize_filename(info.get("title") or info.get("id", "video"))
            target_path = os.path.join(DOWNLOADS_DIR, f"{safe_name}.mp4")
            if final_path != target_path:
                # if target exists, add suffix to avoid collision
                if os.path.exists(target_path):
                    base = os.path.splitext(target_path)[0]
                    target_path = f"{base}_{int(time.time())}.mp4"
                os.replace(final_path, target_path)
                final_path = target_path

            file_size = os.path.getsize(final_path)
            elapsed = time.time() - start_time

            # Build result embed
            embed = discord.Embed(title="✅ Download Complete", color=discord.Color.green())
            embed.add_field(name="📹 Title", value=title, inline=False)
            embed.add_field(name="⏱️ Length", value=duration_str, inline=True)
            # Quality best-effort (height if present)
            height = info.get("height")
            fps = info.get("fps")
            qtxt = f"{height}p" if height else "best"
            if fps:
                qtxt += f" {fps}fps"
            embed.add_field(name="📺 Quality", value=qtxt, inline=True)
            embed.add_field(name="📦 Size", value=sizeof_fmt(file_size), inline=True)
            embed.add_field(name="⏳ Time taken", value=f"{elapsed:.2f}s", inline=True)

            if file_size <= MAX_DISCORD_FILESIZE:
                await status_msg.edit(content="📤 Uploading to Discord…")
                if is_slash:
                    await carrier.followup.send(embed=embed, file=discord.File(final_path))
                else:
                    await carrier.send(embed=embed, file=discord.File(final_path))
            else:
                await status_msg.edit(
                    content=(
                        f"⚠️ File too large for Discord ({sizeof_fmt(file_size)}).\n"
                        f"Uploading to external hosting…\n"
                        f"🗑️ File auto-deletes after **48 hours**."
                    )
                )
                link = await upload_external(final_path)
                if link:
                    # IMPORTANT: No emoji in the URL field value (emojis in field name are fine).
                    embed.add_field(name="External Link", value=link, inline=False)
                    if is_slash:
                        await carrier.followup.send(embed=embed)
                    else:
                        await carrier.send(embed=embed)
                else:
                    msg = "❌ Upload failed. Please try again later."
                    if is_slash:
                        await carrier.followup.send(msg)
                    else:
                        await carrier.send(msg)

        except Exception as e:
            await status_msg.edit(content=f"❌ Download Failed\nError: `{e}`")

        finally:
            # tidy local file if it exists
            try:
                # prefer the mp4 we created
                if "final_path" in locals() and final_path and os.path.exists(final_path):
                    os.remove(final_path)
                # fallback to guess if needed
                elif filename_guess and os.path.exists(filename_guess):
                    os.remove(filename_guess)
            except Exception:
                pass

    # ----- Commands -----
    @app_commands.command(name="urldownload", description="Download a video from a URL")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await self._handle_download(interaction, url, is_slash=True)

    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx: commands.Context, url: str):
        await self._handle_download(ctx, url, is_slash=False)


async def setup(bot):
    await bot.add_cog(URLDownload(bot))
