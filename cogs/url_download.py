import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import os
import time
import asyncio
import math
import re

Loading = "<a:loading:1408941121803124807>"

MAX_DISCORD_FILESIZE = 10 * 1024 * 1024  # 10MB
DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def clean_filename(name: str) -> str:
    name = re.sub(r'[^\w\s.-]', '', name)
    name = re.sub(r'\s+', '_', name).strip('_')
    return name or "file"


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}T{suffix}"


class ProgressHook:
    def __init__(self, message: discord.Message, loop: asyncio.AbstractEventLoop):
        self.message = message
        self.loop = loop
        self.last_update = 0

    def update(self, d):
        if d['status'] == 'downloading':
            percent = d.get("_percent_str", "").strip().replace("%", "")
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded_bytes = d.get("downloaded_bytes", 0)
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)

            try:
                percent_float = float(percent)
            except:
                return

            bar_step = math.floor(percent_float / 10)
            bar = "🟩" * bar_step + "⬛" * (10 - bar_step)
            speed_str = sizeof_fmt(speed) + "/s" if speed else "N/A"
            eta_str = time.strftime("%H:%M:%S", time.gmtime(eta)) if eta else "N/A"
            size_str = f"{sizeof_fmt(downloaded_bytes)}/{sizeof_fmt(total_bytes)}" if total_bytes else f"{sizeof_fmt(downloaded_bytes)}"

            embed = discord.Embed(title="⬇️ Downloading...", color=discord.Color.blurple())
            embed.add_field(name="Progress", value=f"`{bar}` {percent_float:.1f}%", inline=False)
            embed.add_field(name="Size", value=size_str, inline=True)
            embed.add_field(name="Speed", value=speed_str, inline=True)
            embed.add_field(name="ETA", value=eta_str, inline=True)

            now = time.time()
            if now - self.last_update > 1:
                self.last_update = now
                asyncio.run_coroutine_threadsafe(
                    self.message.edit(embed=embed),
                    self.loop
                )
        elif d['status'] == 'finished':
            asyncio.run_coroutine_threadsafe(
                self.message.edit(content="📦 Finalizing...", embed=None),
                self.loop
            )


async def handle_download(bot, interaction_or_ctx, url: str, is_slash: bool):
    start_time = time.time()

    if is_slash:
        await interaction_or_ctx.response.defer(thinking=True)
        status_msg = await interaction_or_ctx.followup.send(embed=discord.Embed(title="🔄 Preparing download..."), wait=True)
    else:
        status_msg = await interaction_or_ctx.send(embed=discord.Embed(title="🔄 Preparing download..."))

    try:
        loop = asyncio.get_running_loop()
        probe_opts = {"format": "bestvideo+bestaudio/best",
                      "quiet": True, "no_warnings": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))

        safe_name = clean_filename(title) + ".mp4"
        filename = os.path.join(DOWNLOADS_DIR, safe_name)

        downloaded = False
        final_size = 0
        final_quality = ""

# HD -> lower quality fallback
        quality_options = [
            "bestvideo[height<=2160]+bestaudio/best",
            "bestvideo[height<=1440]+bestaudio/best",
            "bestvideo[height<=1080]+bestaudio/best",
            "bestvideo[height<=720]+bestaudio/best",
            "bestvideo[height<=480]+bestaudio/best",
            "bestvideo[height<=360]+bestaudio/best",
            "bestvideo[height<=240]+bestaudio/best",
            "worstvideo+bestaudio/worst"
        ]
        for fmt in quality_options:
            ydl_opts = {
                "outtmpl": filename,
                "merge_output_format": "mp4",
                "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
                
                # ✅ makes sure only the single video is downloaded
                "noplaylist": True,
                
                "quiet": True,
                "no_warnings": True,
                "retries": 5,
                "skip_unavailable_fragments": True,
                "ignoreerrors": True,

                "postprocessors": [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4"
                    }
                ],
                
                # ✅ make sure cookies are used
                "cookiefile": "cookies.txt",  # ⚠️ must be Netscape TXT format, not JSON
                
                "cachedir": False,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android"],
                    }
                },
                "progress_hooks": [ProgressHook(status_msg, loop).update],
            }


            if os.path.exists(filename):
                os.remove(filename)

            def download_video():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            await asyncio.to_thread(download_video)

            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                file_size = os.path.getsize(filename)
                if file_size <= MAX_DISCORD_FILESIZE:
                    downloaded = True
                    final_size = file_size
                    final_quality = fmt
                    break
                else:
                    final_size = file_size
                    final_quality = fmt

        if not downloaded:
            await status_msg.edit(embed=discord.Embed(
                title="❌ File Too Large",
                description=f"⛔ Cannot download. File size: {sizeof_fmt(final_size)}\n"
                            "🤩 You can download it manually: https://www.ytmp3.as/",
                color=discord.Color.red()
            ))
            return

        elapsed = time.time() - start_time
        embed = discord.Embed(title="✅ Download Complete", color=discord.Color.green())
        embed.add_field(name="📹 Title", value=title, inline=False)
        embed.add_field(name="⏱️ Length", value=duration_str, inline=True)
        embed.add_field(name="📺 Format Used", value=final_quality, inline=True)
        embed.add_field(name="📦 Size", value=sizeof_fmt(final_size), inline=True)
        embed.add_field(name="⏳ Time taken", value=f"{elapsed:.2f}s", inline=True)

        await status_msg.edit(content=f"{Loading} Uploading to Discord...", embed=None)
        if is_slash:
            await interaction_or_ctx.followup.send(embed=embed, file=discord.File(filename))
        else:
            await interaction_or_ctx.send(embed=embed, file=discord.File(filename))

    except Exception as e:
        await status_msg.edit(embed=discord.Embed(
            title="❌ Download Failed",
            description=f"Error: `{e}`",
            color=discord.Color.red()
        ))
    finally:
        if os.path.exists(filename):
            os.remove(filename)


class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="urldownload", description="Download a video from a URL (MP4 only)")
    @app_commands.describe(url="Video link")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await handle_download(self.bot, interaction, url, is_slash=True)

    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx: commands.Context, url: str):
        await handle_download(self.bot, ctx, url, is_slash=False)


async def setup(bot):
    await bot.add_cog(URLDownload(bot))
