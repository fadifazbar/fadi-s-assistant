import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import os
import random
import time
from datetime import datetime


class Download(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===============================
    # PREFIX COMMAND
    # ===============================
    @commands.command(name="urldownload")
    @commands.has_permissions(manage_messages=True)  # mod-only
    async def urldownload_prefix(self, ctx: commands.Context, url: str):
        """Download a video from a URL and send as MP4"""
        colors = [discord.Color.red(), discord.Color.green(), discord.Color.blurple(),
                  discord.Color.orange(), discord.Color.gold(), discord.Color.purple()]
        color = random.choice(colors)

        start_time = time.perf_counter()

        embed = discord.Embed(
            title="⏬ Downloading...",
            description=f"Fetching video from:\n```{url}```",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        msg = await ctx.send(embed=embed)

        try:
            ydl_opts = {
                'format': 'mp4',
                'outtmpl': 'video.%(ext)s',
                'quiet': True,
                'noplaylist': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            end_time = time.perf_counter()
            elapsed = round(end_time - start_time, 2)

            if os.path.exists("video.mp4"):
                size = os.path.getsize("video.mp4")
                if size <= 25 * 1024 * 1024:
                    file = discord.File("video.mp4", filename="video.mp4")

                    embed = discord.Embed(
                        title="🎬 Download Complete",
                        description=f"Here’s your video:",
                        color=color,
                        timestamp=datetime.utcnow()
                    )
                    embed.set_footer(
                        text=f"Runed by: {ctx.author} | Took {elapsed}s to download",
                        icon_url=ctx.author.display_avatar.url
                    )
                    embed.set_video(url="attachment://video.mp4")

                    await msg.edit(embed=embed, attachments=[file])
                else:
                    await msg.edit(content="❌ File too large for Discord (max 25MB).", embed=None)
                os.remove("video.mp4")
            else:
                await msg.edit(content="❌ Failed to download video.", embed=None)
        except Exception as e:
            await msg.edit(content=f"⚠️ Error: {e}", embed=None)

    # ===============================
    # SLASH COMMAND
    # ===============================
    @app_commands.command(name="urldownload", description="Download a video from a URL and send as MP4")
    @app_commands.checks.has_permissions(manage_messages=True)  # mod-only
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        colors = [discord.Color.red(), discord.Color.green(), discord.Color.blurple(),
                  discord.Color.orange(), discord.Color.gold(), discord.Color.purple()]
        color = random.choice(colors)

        start_time = time.perf_counter()

        embed = discord.Embed(
            title="⏬ Downloading...",
            description=f"Fetching video from:\n```{url}```",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        try:
            ydl_opts = {
                'format': 'mp4',
                'outtmpl': 'video.%(ext)s',
                'quiet': True,
                'noplaylist': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            end_time = time.perf_counter()
            elapsed = round(end_time - start_time, 2)

            if os.path.exists("video.mp4"):
                size = os.path.getsize("video.mp4")
                if size <= 25 * 1024 * 1024:
                    file = discord.File("video.mp4", filename="video.mp4")

                    embed = discord.Embed(
                        title="🎬 Download Complete",
                        description=f"Here’s your video:",
                        color=color,
                        timestamp=datetime.utcnow()
                    )
                    embed.set_footer(
                        text=f"Runed by: {interaction.user} | Took {elapsed}s to download",
                        icon_url=interaction.user.display_avatar.url
                    )
                    embed.set_video(url="attachment://video.mp4")

                    await msg.edit(embed=embed, attachments=[file])
                else:
                    await msg.edit(content="❌ File too large for Discord (max 25MB).", embed=None)
                os.remove("video.mp4")
            else:
                await msg.edit(content="❌ Failed to download video.", embed=None)
        except Exception as e:
            await msg.edit(content=f"⚠️ Error: {e}", embed=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Download(bot))
