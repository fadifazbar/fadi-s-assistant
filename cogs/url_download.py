import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import os
import time
import asyncio
import math
import re

# ✅ Import uploader + deleter from server.py
from server import upload_to_drive, delete_from_drive  

MAX_DISCORD_FILESIZE = 8 * 1024 * 1024  # 8MB
DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def clean_filename(name: str) -> str:
    """Remove emojis + special chars from filename"""
    name = re.sub(r'[^\w\s.-]', '', name)  # keep only safe chars
    name = re.sub(r'\s+', '_', name).strip('_')
    return name or "video"


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
        """This gets called from yt-dlp's thread. We schedule onto bot's loop."""
        if d['status'] == 'downloading':
            percent = d.get("_percent_str", "").strip().replace("%", "")
            try:
                percent_float = float(percent)
            except:
                return

            # progress bar with 🟩⬛
            bar_step = math.floor(percent_float / 10)
            bar = "🟩" * bar_step + "⬛" * (10 - bar_step)

            # progress messages
            if percent_float < 25:
                msg = "Starting download..."
            elif percent_float < 50:
                msg = "Still downloading..."
            elif percent_float < 75:
                msg = "More than halfway!"
            elif percent_float < 100:
                msg = "Almost done..."
            else:
                msg = "Finalizing..."

            now = time.time()
            if now - self.last_update > 1:  # update once per second
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


async def delete_after_48h(file_id: str):
    """Wait 48 hours then delete file from Google Drive"""
    await asyncio.sleep(48 * 3600)  # 48h in seconds
    try:
        delete_from_drive(file_id)
    except Exception as e:
        print(f"[!] Failed to delete file {file_id}: {e}")


async def handle_download(bot, interaction_or_ctx, url: str, is_slash: bool):
    start_time = time.time()

    if is_slash:
        await interaction_or_ctx.response.defer(thinking=True)
        status_msg = await interaction_or_ctx.followup.send("🔄 Fetching video...", wait=True)
    else:
        status_msg = await interaction_or_ctx.reply("🔄 Fetching video...")

    try:
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(DOWNLOADS_DIR, "%(title).200s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)
            duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))
            quality = info.get("format_note", "unknown")

            raw_filename = ydl.prepare_filename(info)
            safe_name = clean_filename(title) + ".mp4"
            filename = os.path.join(DOWNLOADS_DIR, safe_name)

        # Progress hook with event loop reference
        loop = asyncio.get_running_loop()
        hook = ProgressHook(status_msg, loop)
        ydl_opts["progress_hooks"] = [hook.update]

        await status_msg.edit(content="⬇️ Starting download...\n0.0%\n`⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛`")

        def run_download():
            with yt_dlp.YoutubeDL(ydl_opts) as y:
                y.download([url])
            if os.path.exists(raw_filename):
                os.rename(raw_filename, filename)

        await asyncio.to_thread(run_download)

        file_size = os.path.getsize(filename)
        elapsed = time.time() - start_time

        embed = discord.Embed(
            title="✅ Download Complete",
            color=discord.Color.green()
        )
        embed.add_field(name="📹 Title", value=title, inline=False)
        embed.add_field(name="⏱️ Length", value=duration_str, inline=True)
        embed.add_field(name="📺 Quality", value=quality, inline=True)
        embed.add_field(name="📦 Size", value=sizeof_fmt(file_size), inline=True)
        embed.add_field(name="⏳ Time taken", value=f"{elapsed:.2f}s", inline=True)

        if file_size <= MAX_DISCORD_FILESIZE:
            await status_msg.edit(content="📤 Uploading to Discord...")
            if is_slash:
                await interaction_or_ctx.followup.send(embed=embed, file=discord.File(filename))
            else:
                await interaction_or_ctx.send(embed=embed, file=discord.File(filename))
        else:
            await status_msg.edit(
                content=f"⚠️ File too large for Discord ({sizeof_fmt(file_size)}).\n"
                        f"🔗 Uploading to Google Drive..."
            )
            link, file_id = upload_to_drive(filename)  # ✅ upload + return link + file_id
            if link:
                embed.add_field(name="🔗 Direct Download", value=f"[Click here]({link})", inline=False)
                embed.add_field(name="🗑️ Note", value="This file will be deleted after __**48 Hours**__", inline=False)
                if is_slash:
                    await interaction_or_ctx.followup.send(embed=embed)
                else:
                    await interaction_or_ctx.send(embed=embed)

                # schedule deletion after 48h
                asyncio.create_task(delete_after_48h(file_id))
            else:
                await status_msg.edit(content="❌ Upload failed. Please try again later.")

    except Exception as e:
        await status_msg.edit(content=f"❌ Download Failed\nError: `{e}`")

    finally:
        if "filename" in locals() and os.path.exists(filename):
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
