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

EXTERNAL_HOST = "https://fadi-s-assistant-production.up.railway.app"
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
    def __init__(self, message: discord.Message, bot: commands.Bot):
        self.message = message
        self.bot = bot
        self.last_update = 0

    async def update(self, d):
        if d['status'] == 'downloading':
            percent = d.get("_percent_str", "").strip().replace("%", "")
            try:
                percent_float = float(percent)
            except:
                return

            bar_step = math.floor(percent_float / 10)
            bar = "█" * bar_step + "░" * (10 - bar_step)

            now = time.time()
            if now - self.last_update > 1:
                self.last_update = now
                await self.message.edit(
                    content=f"⬇️ Downloading... {percent_float:.1f}%\n`{bar}`"
                )

        elif d['status'] == 'finished':
            await self.message.edit(content="📦 Merging & Finalizing...")


async def handle_download(bot, interaction_or_ctx, url: str, is_slash: bool):
    start_time = time.time()

    if is_slash:
        await interaction_or_ctx.response.defer(thinking=True)
        status_msg = await interaction_or_ctx.followup.send("🔄 Fetching video...", wait=True)
    else:
        status_msg = await interaction_or_ctx.reply("🔄 Fetching video...")

    try:
        ydl_opts = {
            "format": "mp4/bv*+ba/bestvideo+bestaudio/best",
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
            base, ext = os.path.splitext(raw_filename)
            safe_name = clean_filename(title) + ".mp4"
            filename = os.path.join(DOWNLOADS_DIR, safe_name)

        hook = ProgressHook(status_msg, bot)
        ydl_opts["progress_hooks"] = [
            lambda d: asyncio.run_coroutine_threadsafe(hook.update(d), bot.loop)
        ]

        await status_msg.edit(content="⬇️ Downloading... 0.0%\n`░░░░░░░░░░`")

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
                        f"🔗 Uploading to external hosting..."
            )
            link = await upload_external(filename)
            if link:
                embed.add_field(name="🔗 External Link", value=link, inline=False)
                if is_slash:
                    await interaction_or_ctx.followup.send(embed=embed)
                else:
                    await interaction_or_ctx.send(embed=embed)
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
