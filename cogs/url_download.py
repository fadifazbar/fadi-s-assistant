import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp as youtube_dl
import os
import time
import subprocess


# ===============================
# CONFIG
# ===============================
MAX_FILE_SIZE = 8 * 1024 * 1024   # Default 8MB
# If your bot has Nitro boost for bigger uploads, change to:
# MAX_FILE_SIZE = 100 * 1024 * 1024


# ===============================
# COG
# ===============================
class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------
    # Helper: Compress until under limit
    # ---------------------------
    async def compress_video(self, input_path: str, output_path: str, max_size=MAX_FILE_SIZE):
        crf = 28  # start quality
        loop = asyncio.get_running_loop()

        while True:
            def _compress():
                cmd = [
                    "ffmpeg", "-i", input_path,
                    "-vcodec", "libx264", "-crf", str(crf),
                    "-preset", "fast", "-y", output_path
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return os.path.getsize(output_path)

            size = await loop.run_in_executor(None, _compress)

            if size <= max_size:
                return output_path

            crf += 2
            if crf > 50:  # don’t make it potato quality
                raise ValueError("Video too large to compress reasonably.")

    # ---------------------------
    # Helper: Download video with progress
    # ---------------------------
    async def download_video(self, url: str, output_path: str, progress_msg: discord.Message = None):
        loop = asyncio.get_running_loop()
        progress = {"percent": 0.0}

        def progress_hook(d):
            if d["status"] == "downloading":
                percent = d.get("_percent_str", "0%").strip()
                try:
                    progress["percent"] = float(percent.replace("%", ""))
                except:
                    progress["percent"] = 0.0

        def _download():
            ydl_opts = {
                "outtmpl": output_path,
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return output_path

        async def updater():
            while progress["percent"] < 100:
                bar_filled = int(progress["percent"] // 10)
                bar = "🟥" * bar_filled + "⬛" * (10 - bar_filled)
                try:
                    await progress_msg.edit(content=f"**Downloading:** {progress['percent']:.1f}% / 100%\n{bar}")
                except:
                    pass
                await asyncio.sleep(2)

        updater_task = asyncio.create_task(updater())
        final_path = await loop.run_in_executor(None, _download)
        updater_task.cancel()
        return final_path

    # ---------------------------
    # Main logic
    # ---------------------------
    async def send_video(self, ctx_or_inter, url: str, user, is_slash=False):
        start_time = time.time()
        filename = "video.mp4"
        compressed = "video_compressed.mp4"

        embed = discord.Embed(title="🎥 Fetching Video", description=f"From: `{url}`", color=discord.Color.blue())
        if is_slash:
            await ctx_or_inter.response.send_message(embed=embed)
            msg = await ctx_or_inter.original_response()
        else:
            msg = await ctx_or_inter.send(embed=embed)

        try:
            # Download with progress bar
            final_path = await self.download_video(url, filename, msg)

            # Compress if needed
            if os.path.getsize(final_path) > MAX_FILE_SIZE:
                final_path = await self.compress_video(final_path, compressed, MAX_FILE_SIZE)

            # Send final video
            elapsed = round(time.time() - start_time, 2)
            embed = discord.Embed(title="✅ Download Complete", color=discord.Color.green())
            embed.set_footer(text=f"Run by: {user} | Took {elapsed}s", icon_url=user.display_avatar.url)

            file = discord.File(final_path, filename="video.mp4")

            await msg.edit(content="", embed=embed, attachments=[file])

        except Exception as e:
            embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await msg.edit(content="", embed=embed)

        finally:
            if os.path.exists(filename):
                os.remove(filename)
            if os.path.exists(compressed):
                os.remove(compressed)

    # ---------------------------
    # Prefix command
    # ---------------------------
    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx, url: str):
        await self.send_video(ctx, url, ctx.author, is_slash=False)

    # ---------------------------
    # Slash command
    # ---------------------------
    @app_commands.command(name="urldownload", description="Download a video from a URL and upload it as MP4")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await self.send_video(interaction, url, interaction.user, is_slash=True)


# ===============================
# SETUP
# ===============================
async def setup(bot):
    await bot.add_cog(URLDownload(bot))
