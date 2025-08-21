import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp as youtube_dl
import os
import aiohttp
import time

class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===============================
    # Helper: Determine upload limit from Nitro level
    # ===============================
    def get_upload_limit(self, guild: discord.Guild) -> int:
        if guild.premium_tier == 0:
            return 8 * 1024 * 1024
        elif guild.premium_tier == 1:
            return 50 * 1024 * 1024
        else:
            return 100 * 1024 * 1024

    # ===============================
    # Helper: Progress hook for yt-dlp
    # ===============================
    async def progress_hook(self, d, message, start_time):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0.0%').strip()
            percent_val = float(percent.replace('%', ''))
            bar_filled = int(percent_val // 10)
            bar = "🟥" * bar_filled + "⬛" * (10 - bar_filled)
            elapsed = round(time.time() - start_time, 1)
            embed = discord.Embed(
                title="⬇️ Downloading...",
                description=f"**{percent} / 100%**\n{bar}\n⏱️ Elapsed: `{elapsed}s`",
                color=discord.Color.yellow()
            )
            await message.edit(embed=embed)

    # ===============================
    # Helper: Download + compress
    # ===============================
    async def download_and_compress(self, url, output_path, message, start_time):
        loop = asyncio.get_running_loop()

        def _download():
            ydl_opts = {
                'outtmpl': output_path,
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'progress_hooks': [lambda d: asyncio.run_coroutine_threadsafe(
                    self.progress_hook(d, message, start_time), loop)],
                'quiet': True,
                'noplaylist': True
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            return info

        info = await loop.run_in_executor(None, _download)
        return info

    # ===============================
    # Helper: Upload externally (transfer.sh)
    # ===============================
    async def upload_external(self, filepath: str) -> str:
        async with aiohttp.ClientSession() as session:
            with open(filepath, 'rb') as f:
                async with session.put(f"https://transfer.sh/{os.path.basename(filepath)}", data=f) as resp:
                    return await resp.text()

    # ===============================
    # Core: Handle video send
    # ===============================
    async def send_video(self, ctx, url, user):
        output_path = "video.mp4"
        start_time = time.time()

        embed = discord.Embed(
            title="🔄 Fetching Video...",
            description=f"Fetching video from:\n```{url}```",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Requested by {user}", icon_url=user.display_avatar.url)
        message = await ctx.reply(embed=embed) if isinstance(ctx, commands.Context) else await ctx.response.send_message(embed=embed)

        try:
            info = await self.download_and_compress(url, output_path, message, start_time)
            file_size = os.path.getsize(output_path)
            limit = self.get_upload_limit(ctx.guild)

            duration = time.strftime("%H:%M:%S", time.gmtime(info.get("duration", 0)))
            quality = info.get("format", "Unknown")
            elapsed = round(time.time() - start_time, 1)

            if file_size <= limit:
                file = discord.File(output_path, filename="video.mp4")
                embed = discord.Embed(
                    title="✅ Download Complete",
                    color=discord.Color.green()
                )
                embed.add_field(name="📏 Video Length", value=duration, inline=True)
                embed.add_field(name="🎞️ Quality", value=quality, inline=True)
                embed.add_field(name="⏱️ Time Taken", value=f"{elapsed}s", inline=True)
                embed.set_footer(text=f"Requested by {user}", icon_url=user.display_avatar.url)
                await message.edit(embed=embed, attachments=[file])
            else:
                external_link = await self.upload_external(output_path)
                embed = discord.Embed(
                    title="✅ Download Complete",
                    description=(
                        f"⚠️ File too large for Discord (server limit: {limit//1024//1024}MB "
                        f"(depending on the server's boost level))\n"
                        f"Download it here: {external_link}"
                    ),
                    color=discord.Color.red()
                )
                embed.add_field(name="📏 Video Length", value=duration, inline=True)
                embed.add_field(name="🎞️ Quality", value=quality, inline=True)
                embed.add_field(name="⏱️ Time Taken", value=f"{elapsed}s", inline=True)
                embed.set_footer(text=f"Requested by {user}", icon_url=user.display_avatar.url)
                await message.edit(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Download Failed",
                description=f"Error: {e}",
                color=discord.Color.red()
            )
            await message.edit(embed=embed)

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    # ===============================
    # Prefix Command
    # ===============================
    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx, url: str):
        await self.send_video(ctx, url, ctx.author)

    # ===============================
    # Slash Command
    # ===============================
    @app_commands.command(name="urldownload", description="Download a video from a URL")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await self.send_video(interaction, url, interaction.user)

async def setup(bot):
    await bot.add_cog(URLDownload(bot))
