import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import os
import time
import asyncio
import math
import re

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


async def handle_download(bot, interaction_or_ctx, url: str, download_type: str, is_slash: bool):
    if not download_type:
        msg = "📝 Please Choose A Type. Mp3 Or Mp4"
        if is_slash:
            await interaction_or_ctx.response.send_message(msg, ephemeral=True)
        else:
            await interaction_or_ctx.send(msg)
        return

    download_type = download_type.lower()
    start_time = time.time()

    if is_slash:
        await interaction_or_ctx.response.defer(thinking=True)
        status_msg = await interaction_or_ctx.followup.send(embed=discord.Embed(title="🔄 Preparing download..."), wait=True)
    else:
        status_msg = await interaction_or_ctx.send(embed=discord.Embed(title="🔄 Preparing download..."))

    try:
        loop = asyncio.get_running_loop()
        probe_opts = {"format": "bestaudio/best" if download_type == "mp3" else "bestvideo+bestaudio/best",
                      "quiet": True, "no_warnings": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))

        ext = "mp3" if download_type == "mp3" else "mp4"
        safe_name = clean_filename(title) + f".{ext}"
        filename = os.path.join(DOWNLOADS_DIR, safe_name)

        downloaded = False
        final_size = 0
        final_quality = ""

        if download_type == "mp4":
            # HD -> 4K fallback
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
                    "format": fmt,
                    "merge_output_format": "mp4",
                    "outtmpl": filename,
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                    "progress_hooks": [ProgressHook(status_msg, loop).update]
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

        else:  # mp3
            # Try progressively lower bitrates until it fits under 10MB
            bitrates = ["192", "128", "96", "64", "32"]
            for br in bitrates:
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": filename,
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                    "progress_hooks": [ProgressHook(status_msg, loop).update],
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": br
                    }],
                    "postprocessor_hooks": [lambda d: print(f"POST: {d}")]
                }

                if os.path.exists(filename):
                    os.remove(filename)

                def download_audio():
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                    except Exception:
                        pass

                await asyncio.to_thread(download_audio)

                # 🔹 Wait for FFmpeg to finish and file to be written
                for _ in range(20):  # up to ~10 seconds
                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        break
                    await asyncio.sleep(0.5)

                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    file_size = os.path.getsize(filename)
                    final_size = file_size
                    final_quality = f"Audio MP3 ({br}kbps)"

                    if file_size <= MAX_DISCORD_FILESIZE:
                        downloaded = True
                        break

        elapsed = time.time() - start_time


        if not downloaded:
            await status_msg.edit(embed=discord.Embed(
                title="❌ File Too Large",
                description=f"⛔ Cannot download. File size: {sizeof_fmt(final_size)}\n"
                            "🤩 You can download it manually: https://www.ytmp3.as/",
                color=discord.Color.red()
            ))
            return

        embed = discord.Embed(title="✅ Download Complete", color=discord.Color.green())
        embed.add_field(name="📹 Title", value=title, inline=False)
        embed.add_field(name="⏱️ Length", value=duration_str, inline=True)
        embed.add_field(name="📺 Format Used", value=final_quality, inline=True)
        embed.add_field(name="📦 Size", value=sizeof_fmt(final_size), inline=True)
        embed.add_field(name="⏳ Time taken", value=f"{elapsed:.2f}s", inline=True)

        await status_msg.edit(content="📤 Uploading to Discord...", embed=None)
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

    @app_commands.command(name="urldownload", description="Download a video or audio from a URL")
    @app_commands.describe(url="Video/Audio link", type="Choose MP3 or MP4")
    @app_commands.choices(type=[
        app_commands.Choice(name="MP3", value="mp3"),
        app_commands.Choice(name="MP4", value="mp4")
    ])
    async def urldownload_slash(self, interaction: discord.Interaction, url: str, type: app_commands.Choice[str] = None):
        download_type = type.value if type else None
        await handle_download(self.bot, interaction, url, download_type, is_slash=True)

    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx: commands.Context, url: str, download_type: str = None):
        if not download_type or download_type.lower() not in ["mp3", "mp4"]:
            await ctx.send("📝 Please Choose A Type. Mp3 Or Mp4")
            return
        await handle_download(self.bot, ctx, url, download_type.lower(), is_slash=False)


async def setup(bot):
    await bot.add_cog(URLDownload(bot))
