import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import os
import time


class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def download_video(self, url: str, output_path: str, progress_callback):
        loop = asyncio.get_running_loop()

        def _download():
            ydl_opts = {
                "outtmpl": output_path,
                "format": "mp4/best",
                "quiet": True,
                "no_warnings": True,
                "retries": 3,
                "progress_hooks": [progress_callback],  # ✅ hook for progress
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return output_path

        return await loop.run_in_executor(None, _download)

    async def send_video(self, ctx_or_interaction, url: str, user):
        output_path = "video.mp4"
        start = time.time()

        # Initial embed
        embed = discord.Embed(
            title="📥 Downloading...",
            description=f"From: {url}\n\n`0.0% / 100%`\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
            color=discord.Color.yellow(),
        )
        if isinstance(ctx_or_interaction, commands.Context):
            msg = await ctx_or_interaction.send(embed=embed)
        else:
            await ctx_or_interaction.response.send_message(embed=embed)
            msg = await ctx_or_interaction.original_response()

        last_bar_step = 0  # track when to update bar

        # Progress hook
        async def progress_hook(d):
            nonlocal last_bar_step

            if d["status"] == "downloading":
                percent = d.get("_percent_str", "0.0%").strip()
                try:
                    percent_val = float(d["_percent_str"].replace("%", "").strip())
                except:
                    percent_val = 0.0

                # build bar (update only each +10%)
                bar_step = int(percent_val // 10)
                bar = "🟥" * bar_step + "⬛" * (10 - bar_step)

                # only edit if % changed
                embed.description = f"From: {url}\n\n`{percent} / 100%`\n{bar}"
                try:
                    await msg.edit(embed=embed)
                except:
                    pass

        # Download
        try:
            final_path = await self.download_video(url, output_path, lambda d: asyncio.run_coroutine_threadsafe(progress_hook(d), self.bot.loop).result())

            # Validate
            if not os.path.exists(final_path) or os.path.getsize(final_path) < 100000:
                raise Exception("Download failed or empty file")

            file = discord.File(final_path, filename="video.mp4")

            end = time.time()
            elapsed = round(end - start, 2)

            embed = discord.Embed(
                title="✅ Download Complete", color=discord.Color.green()
            )
            embed.set_footer(
                text=f"Run by: {user} | Took {elapsed}s",
                icon_url=user.display_avatar.url,
            )

            if isinstance(ctx_or_interaction, commands.Context):
                await msg.edit(embed=embed, attachments=[file])
            else:
                await ctx_or_interaction.edit_original_response(embed=embed, attachments=[file])

            os.remove(final_path)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Download Failed", description=f"Error: {str(e)}", color=discord.Color.red()
            )
            if isinstance(ctx_or_interaction, commands.Context):
                await msg.edit(embed=embed)
            else:
                await ctx_or_interaction.edit_original_response(embed=embed)

    # PREFIX COMMAND
    @commands.command(name="urldownload")
    async def urldownload_prefix(self, ctx, url: str):
        await self.send_video(ctx, url, ctx.author)

    # SLASH COMMAND
    @app_commands.command(name="urldownload", description="Download a video from a link")
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        await self.send_video(interaction, url, interaction.user)


async def setup(bot):
    await bot.add_cog(URLDownload(bot))
