import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import os
import time
import asyncio
import math
import re

MAX_DISCORD_FILESIZE = 8 * 1024 * 1024  # 8MB
DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def clean_filename(name: str) -> str:
    """Remove emojis + special chars from filename"""
    name = re.sub(r'[^\w\s.-]', '', name)
    name = re.sub(r'\s+', '_', name).strip('_')
    return name or "video"


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}T{suffix}"


class ProgressHook:
    """Handles yt-dlp progress updates"""
    def __init__(self, message: discord.Message, loop: asyncio.AbstractEventLoop):
        self.message = message
        self.loop = loop
        self.last_update = 0

    def update(self, d):
        if d['status'] == 'downloading':
            percent = d.get("_percent_str", "").strip().replace("%", "")
            try:
                percent_float = float(percent)
            except:
                return

            bar_step = math.floor(percent_float / 10)
            bar = "🟩" * bar_step + "⬛" * (10 - bar_step)

            msg = "Starting download..." if percent_float < 25 else \
                  "Still downloading..." if percent_float < 50 else \
                  "More than halfway!" if percent_float < 75 else \
                  "Almost done..." if percent_float < 100 else \
                  "Finalizing..."

            now = time.time()
            if now - self.last_update > 1:
                self.last_update = now
                asyncio.run_coroutine_threadsafe(
                    self.message.edit(
                        content=f"⬇️ {msg}\n{percent_float:.1f}%\n`{bar}`"
                    ),
                    self.loop
                )
        elif d['status'] == 'finished':
            asyncio.run_coroutine_threadsafe(
                self.message.edit(content="📦 Merging & Finalizing..."),
                self.loop
            )


async def handle_download(bot, interaction_or_ctx, url: str, is_slash: bool):
    start_time = time.time()
    if is_slash:
        await interaction_or_ctx.response.defer(thinking=True)
        status_msg = await interaction_or_ctx.followup.send("🔄 Fetching video...", wait=True)
    else:
        status_msg = await interaction_or_ctx.reply("🔄 Fetching video...")

    try:
        loop = asyncio.get_running_loop()

        # Step 1: Probe video info
        probe_opts = {"format": "bestvideo+bestaudio/best", "quiet": True, "no_warnings": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))

        safe_name = clean_filename(title) + ".mp4"
        filename = os.path.join(DOWNLOADS_DIR, safe_name)

        # Step 2: Try multiple qualities to fit 8MB
        quality_options = [
            "bestvideo+bestaudio/best",
            "480p/best",
            "360p/best",
            "240p/best",
            "worstvideo+bestaudio/worst"
        ]
        downloaded = False
        final_size = 0
        final_quality = ""

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

            # Remove file if exists
            if os.path.exists(filename):
                os.remove(filename)

            await status_msg.edit(content=f"⬇️ Trying quality: {fmt} ...")
            def download_video():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            await asyncio.to_thread(download_video)

            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                if file_size <= MAX_DISCORD_FILESIZE:
                    downloaded = True
                    final_size = file_size
                    final_quality = fmt
                    break  # success, stop trying
                else:
                    final_size = file_size  # keep last attempt
                    final_quality = fmt

        elapsed = time.time() - start_time

        embed = discord.Embed(title="✅ Download Complete", color=discord.Color.green())
        embed.add_field(name="📹 Title", value=title, inline=False)
        embed.add_field(name="⏱️ Length", value=duration_str, inline=True)
        embed.add_field(name="📺 Quality Used", value=final_quality, inline=True)
        embed.add_field(name="📦 Size", value=sizeof_fmt(final_size), inline=True)
        embed.add_field(name="⏳ Time taken", value=f"{elapsed:.2f}s", inline=True)

        # Step 3: Send or fail
        if downloaded:
            await status_msg.edit(content="📤 Uploading to Discord...")
            if is_slash:
                await interaction_or_ctx.followup.send(embed=embed, file=discord.File(filename))
            else:
                await interaction_or_ctx.send(embed=embed, file=discord.File(filename))
        else:
            await status_msg.edit(content=(
                f"❌ I cannot download this file. It's too large for the server's boost level "
                f"({sizeof_fmt(final_size)})\n"
                "You can download this video by using https://www.ytmp3.as to download it either using mp3 or mp4!"
            ))

    except Exception as e:
        await status_msg.edit(content=f"❌ Download Failed\nError: `{e}`")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="urldownload", description="Download a video from a URL")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await handle_download(self.bot, interaction, url, is_slash=True)

    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx: commands.Context, url: str):
        await handle_download(self.bot, ctx, url, is_slash=False)


async def setup(bot):
    await bot.add_cog(URLDownload(bot))
