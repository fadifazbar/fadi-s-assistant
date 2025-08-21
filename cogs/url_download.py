import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import os
import asyncio
import random
import time
import subprocess

class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def download_and_compress(self, url: str, output_path: str, max_size: int = 8 * 1024 * 1024):
        """Download video and compress if needed"""
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4'
        }

        # Download video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # If file too large → compress
        while os.path.getsize(output_path) > max_size:
            compressed_path = output_path.replace(".mp4", "_compressed.mp4")

            # Lower resolution + bitrate to shrink file
            cmd = [
                "ffmpeg", "-i", output_path,
                "-vf", "scale=iw/2:ih/2",  # half resolution
                "-b:v", "800k",  # lower bitrate
                "-b:a", "96k",   # lower audio bitrate
                "-y", compressed_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            os.remove(output_path)
            os.rename(compressed_path, output_path)

        return output_path

    async def send_video(self, ctx_or_interaction, url: str, user):
        start_time = time.time()
        embed = discord.Embed(
            title="📥 Fetching video...",
            description=f"From: `{url}`",
            color=random.choice([discord.Color.red(), discord.Color.blue(), discord.Color.green(), discord.Color.orange()])
        )
        msg = await (ctx_or_interaction.send(embed=embed) if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.response.send_message(embed=embed))

        output_path = "video.mp4"
        try:
            if os.path.exists(output_path):
                os.remove(output_path)

            final_path = await self.download_and_compress(url, output_path)

            elapsed = round(time.time() - start_time, 2)
            file = discord.File(final_path, filename="video.mp4")

            embed = discord.Embed(
                title="✅ Download Complete",
                description=f"Here is your video from: `{url}`",
                color=random.choice([discord.Color.red(), discord.Color.blue(), discord.Color.green(), discord.Color.orange()])
            )
            embed.set_footer(text=f"Run by: {user} | Took {elapsed}s", icon_url=user.display_avatar.url)

            if isinstance(ctx_or_interaction, commands.Context):
                await msg.edit(embed=embed, attachments=[file])
            else:
                await msg.edit(embed=embed, attachments=[file])

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to download: {e}",
                color=discord.Color.red()
            )
            if isinstance(ctx_or_interaction, commands.Context):
                await msg.edit(embed=error_embed)
            else:
                await msg.edit(embed=error_embed)

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    # ===============================
    # PREFIX COMMAND
    # ===============================
    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx: commands.Context, url: str):
        await self.send_video(ctx, url, ctx.author)

    # ===============================
    # SLASH COMMAND
    # ===============================
    @app_commands.command(name="urldownload", description="Download a video from any URL")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await self.send_video(interaction, url, interaction.user)


async def setup(bot):
    await bot.add_cog(URLDownload(bot))
