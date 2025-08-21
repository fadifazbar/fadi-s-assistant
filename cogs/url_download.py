import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio
import os
import time


class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def download_and_compress(self, url: str, output_path: str, progress_callback):
        loop = asyncio.get_running_loop()

        def _download():
            ydl_opts = {
                'outtmpl': output_path,
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [progress_callback]
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return output_path

        final_path = await loop.run_in_executor(None, _download)
        return final_path

    def build_progress_bar(self, percent: float) -> str:
        blocks = 10
        filled_blocks = int((percent / 100) * blocks)
        bar = "🟥" * filled_blocks + "⬛" * (blocks - filled_blocks)
        return f"{percent:.1f}% / 100%\n{bar}"

    async def send_video(self, ctx_or_inter, url: str, requester, is_slash=False):
        start_time = time.time()
        output_path = "video.mp4"

        # Initial embed
        embed = discord.Embed(
            title="Downloading...",
            description=f"Fetching video from: `{url}`",
            color=discord.Color.red()
        )
        if is_slash:
            await ctx_or_inter.response.send_message(embed=embed)
            message = await ctx_or_inter.original_response()
        else:
            message = await ctx_or_inter.send(embed=embed)

        last_update = {"percent": 0}

        def progress_hook(d):
            if d["status"] == "downloading":
                percent = d.get("_percent_str", "0%").strip()
                try:
                    percent = float(percent.replace("%", ""))
                except ValueError:
                    percent = 0.0

                # Update only every 10%
                if percent - last_update["percent"] >= 10:
                    last_update["percent"] = percent
                    new_embed = discord.Embed(
                        title="Downloading...",
                        description=self.build_progress_bar(percent),
                        color=discord.Color.orange()
                    )
                    asyncio.run_coroutine_threadsafe(message.edit(embed=new_embed), self.bot.loop)

        try:
            final_path = await self.download_and_compress(url, output_path, progress_hook)

            # Send result
            elapsed = round(time.time() - start_time, 2)
            file = discord.File(final_path, filename="video.mp4")

            result_embed = discord.Embed(
                title="✅ Download Complete",
                color=discord.Color.green()
            )
            result_embed.set_footer(
                text=f"Runed by: {requester} | Took {elapsed}s",
                icon_url=requester.display_avatar.url
            )
            await message.edit(embed=result_embed, attachments=[file])

            os.remove(final_path)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=str(e),
                color=discord.Color.red()
            )
            await message.edit(embed=error_embed)

    # Prefix command
    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx, url: str):
        await self.send_video(ctx, url, ctx.author, is_slash=False)

    # Slash command
    @app_commands.command(name="urldownload", description="Download a video from a link")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await self.send_video(interaction, url, interaction.user, is_slash=True)


async def setup(bot):
    await bot.add_cog(URLDownload(bot))
