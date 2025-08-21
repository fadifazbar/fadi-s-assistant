import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import aiohttp
import os
import time
import asyncio
import math

# ---------- CONFIG ----------
# ✅ Use ONLY your Railway app base domain here
EXTERNAL_HOST = "https://fadi-s-assistant-production.up.railway.app"
MAX_DISCORD_FILESIZE = 8 * 1024 * 1024  # 8MB
# ----------------------------

def sizeof_fmt(num, suffix="B"):
    """Convert bytes → human-readable format."""
    for unit in ["", "K", "M", "G"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}T{suffix}"

async def upload_external(file_path: str):
    """Upload file to external hosting and return link."""
    upload_url = f"{EXTERNAL_HOST}/upload"
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("file", f, filename=os.path.basename(file_path))
            async with session.post(upload_url, data=data) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    return res.get("file_url")
                return None

class ProgressHook:
    """Handles yt-dlp progress reporting with bar + %."""
    def __init__(self, message: discord.Message):
        self.message = message
        self.last_update = 0
        self.last_bar_step = -1

    async def hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get("_percent_str", "").strip().replace("%", "")
            try:
                percent_float = float(percent)
            except:
                return

            bar_step = math.floor(percent_float / 10)
            bar = "🟩" * bar_step + "⬛" * (10 - bar_step)

            now = time.time()
            if now - self.last_update > 1:
                self.last_update = now
                await self.message.edit(
                    content=f"⬇️ Downloading... {percent_float:.1f}%/100%\n{bar}"
                )

        elif d['status'] == 'finished':
            await self.message.edit(content="📦 Merging & Finalizing...")

class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="urldownload", description="Download a video from a URL")
    async def urldownload(self, interaction: discord.Interaction, url: str):
        start_time = time.time()

        await interaction.response.defer(thinking=True)
        status_msg = await interaction.followup.send("🔄 Fetching video...", wait=True)

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": "downloads/%(title).200s.%(ext)s",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)
                duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))
                quality = info.get("format_note", "unknown")
                filename = ydl.prepare_filename(info)

            progress = ProgressHook(status_msg)
            ydl_opts["progress_hooks"] = [lambda d: asyncio.create_task(progress.hook(d))]

            await status_msg.edit(content="⬇️ Downloading... 0.0%/100%\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

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
                await interaction.followup.send(embed=embed, file=discord.File(filename))
            else:
                await status_msg.edit(
                    content=f"⚠️ File too large for Discord ({sizeof_fmt(file_size)}).\n"
                            f"🔗 Uploading to external hosting...\n"
                            f"🗑️ File auto-deletes after __**48 hours**__."
                )

                link = await upload_external(filename)

                if link:
                    embed.add_field(name="🔗 External Link", value=link, inline=False)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("❌ Upload failed. Please try again later.")

        except Exception as e:
            await status_msg.edit(content=f"❌ Download Failed\nError: `{e}`")

        finally:
            if "filename" in locals() and os.path.exists(filename):
                os.remove(filename)

async def setup(bot):
    await bot.add_cog(URLDownload(bot))
