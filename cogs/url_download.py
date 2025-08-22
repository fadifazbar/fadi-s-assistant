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

async def upload_external(file_path: str):
    """Upload file to external hosting and return direct-download link."""
    upload_url = f"{EXTERNAL_HOST}/upload"
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("file", f, filename=os.path.basename(file_path))
            async with session.post(upload_url, data=data) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    filename = os.path.basename(file_path)
                    # 🔽 Force auto-download link instead of preview
                    return f"{EXTERNAL_HOST}/download/{filename}"
                return None

class ProgressHook:
    """Handles yt-dlp progress reporting with bar + %."""
    def __init__(self, message: discord.Message, bot: commands.Bot):
        self.message = message
        self.bot = bot
        self.last_update = 0

    def hook(self, d):
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
                asyncio.run_coroutine_threadsafe(
                    self.message.edit(
                        content=f"⬇️ Downloading... {percent_float:.1f}%/100%\n{bar}"
                    ),
                    self.bot.loop
                )

        elif d['status'] == 'finished':
            asyncio.run_coroutine_threadsafe(
                self.message.edit(content="📦 Merging & Finalizing..."),
                self.bot.loop
            )


async def handle_download(interaction_or_ctx, url: str, is_slash: bool, bot: commands.Bot):
    """Shared logic for both slash + prefix command."""
    start_time = time.time()

    # Send first message
    if is_slash:
        await interaction_or_ctx.response.defer(thinking=True)
        status_msg = await interaction_or_ctx.followup.send("🔄 Fetching video...", wait=True)
    else:
        status_msg = await interaction_or_ctx.reply("🔄 Fetching video...")

    ydl_opts = {
        "format": "bv*+ba/bestvideo+bestaudio/best",
        "outtmpl": os.path.join(DOWNLOADS_DIR, "%(title).200s.%(ext)s"),
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

        # Progress
        progress = ProgressHook(status_msg, bot)
        ydl_opts["progress_hooks"] = [progress.hook]

        await status_msg.edit(content="⬇️ Downloading... 0.0%\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛")

        # Run download in thread (non-blocking!)
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

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
                        f"🔗 Uploading to external hosting...\n"
                        f"🗑️ File auto-deletes after __**48 hours**__."
            )

            link = await upload_external(filename)

            if link:
                embed.add_field(name="🔗 Direct Download Link", value=link, inline=False)
                if is_slash:
                    await interaction_or_ctx.followup.send(embed=embed)
                else:
                    await interaction_or_ctx.send(embed=embed)
            else:
                if is_slash:
                    await interaction_or_ctx.followup.send("❌ Upload failed. Please try again later.")
                else:
                    await interaction_or_ctx.send("❌ Upload failed. Please try again later.")

    except Exception as e:
        await status_msg.edit(content=f"❌ Download Failed\nError: `{e}`")

    finally:
        if "filename" in locals() and os.path.exists(filename):
            os.remove(filename)

class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash command
    @app_commands.command(name="urldownload", description="Download a video from a URL")
    async def urldownload(self, interaction: discord.Interaction, url: str):
        await handle_download(interaction, url, is_slash=True, bot=self.bot)

    # Prefix command
    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx: commands.Context, url: str):
        await handle_download(ctx, url, is_slash=False, bot=self.bot)

async def setup(bot):
    await bot.add_cog(URLDownload(bot))
