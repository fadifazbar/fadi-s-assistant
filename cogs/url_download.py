import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import os
import time
import math
import tempfile
import random
from datetime import datetime
import asyncio


class Download(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- helpers ----------
    def _rand_color(self) -> discord.Color:
        colors = [
            discord.Color.red(),
            discord.Color.green(),
            discord.Color.blurple(),
            discord.Color.orange(),
            discord.Color.gold(),
            discord.Color.purple()
        ]
        return random.choice(colors)

    def _ydl_opts(self, out_no_ext: str) -> dict:
        # Produce mp4 when possible; requires ffmpeg to be installed on the host
        return {
            "format": "bv*+ba/b[ext=mp4]/b/bestaudio/best",
            "outtmpl": out_no_ext + ".%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
            ],
            # Make failures clearer instead of silently skipping
            "ignoreerrors": False,
            "retries": 2,
        }

    async def _download_video(self, url: str, tmpdir: str) -> str:
        """
        Downloads the video to tmpdir and returns the final mp4 path.
        Raises on error.
        """
        base = os.path.join(tmpdir, "video")
        opts = self._ydl_opts(base)

        def _run():
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

        # Offload to a thread so we don't block the event loop
        await asyncio.to_thread(_run)

        # Find resulting file (prefer .mp4)
        candidates = []
        for name in os.listdir(tmpdir):
            if name.lower().endswith((".mp4", ".mkv", ".webm", ".mov", ".m4v")):
                candidates.append(os.path.join(tmpdir, name))

        if not candidates:
            raise RuntimeError("Download finished but no media file was produced.")

        # If not mp4, try to convert filename choice (yt-dlp should already convert)
        # Prefer mp4 if present
        for p in candidates:
            if p.lower().endswith(".mp4"):
                return p
        # Fall back to first candidate
        return candidates[0]

    def _fmt_elapsed(self, secs: float) -> str:
        # Pretty: 1.23s, 12.3s, 1m 02s, 3m 12s, etc.
        if secs < 60:
            return f"{secs:.2f}s" if secs < 10 else f"{secs:.1f}s"
        m = int(secs // 60)
        s = int(round(secs - m * 60))
        return f"{m}m {s:02d}s"

    # ===============================
    # PREFIX COMMAND
    # ===============================
    @commands.command(name="urldownload")
    @commands.has_permissions(manage_messages=True)  # mod-only
    async def urldownload_prefix(self, ctx: commands.Context, url: str):
        """Download a video from a URL and send as MP4"""
        color = self._rand_color()
        start = time.perf_counter()

        # Step 1: send placeholder
        embed = discord.Embed(
            title="⏬ Downloading...",
            description=f"Fetching video from:\n```{url}```",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        msg = await ctx.send(embed=embed)

        # Use a temp directory per request
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                path = await self._download_video(url, tmpdir)
                elapsed = self._fmt_elapsed(time.perf_counter() - start)

                # Size gate (use guild limit if present)
                guild_limit = getattr(ctx.guild, "filesize_limit", 25 * 1024 * 1024)
                size = os.path.getsize(path)
                if size > guild_limit:
                    too_big = f"❌ File too large for this server (limit: {math.floor(guild_limit/1024/1024)}MB)."
                    await msg.edit(content=too_big, embed=None)
                    return

                # Step 2: edit original embed to 'complete'
                done = discord.Embed(
                    title="🎬 Download Complete",
                    description="Here’s your video:",
                    color=color,
                    timestamp=datetime.utcnow()
                )
                done.set_footer(
                    text=f"Runed by: {ctx.author} | Took {elapsed} to download",
                    icon_url=ctx.author.display_avatar.url
                )
                await msg.edit(embed=done)

                # Step 3: send the file (Discord will render the video player)
                file = discord.File(path, filename=os.path.basename(path))
                await ctx.send(file=file)

            except Exception as e:
                await msg.edit(content=f"⚠️ Error: {e}", embed=None)

    # ===============================
    # SLASH COMMAND
    # ===============================
    @app_commands.command(name="urldownload", description="Download a video from a URL and send as MP4")
    @app_commands.checks.has_permissions(manage_messages=True)  # mod-only
    async def urldownload_slash(self, interaction: discord.Interaction, url: str):
        color = self._rand_color()
        start = time.perf_counter()

        # Step 1: send placeholder
        embed = discord.Embed(
            title="⏬ Downloading...",
            description=f"Fetching video from:\n```{url}```",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                path = await self._download_video(url, tmpdir)
                elapsed = self._fmt_elapsed(time.perf_counter() - start)

                guild_limit = getattr(interaction.guild, "filesize_limit", 25 * 1024 * 1024)
                size = os.path.getsize(path)
                if size > guild_limit:
                    too_big = f"❌ File too large for this server (limit: {math.floor(guild_limit/1024/1024)}MB)."
                    await msg.edit(content=too_big, embed=None)
                    return

                # Step 2: edit original embed to 'complete'
                done = discord.Embed(
                    title="🎬 Download Complete",
                    description="Here’s your video:",
                    color=color,
                    timestamp=datetime.utcnow()
                )
                done.set_footer(
                    text=f"Runed by: {interaction.user} | Took {elapsed} to download",
                    icon_url=interaction.user.display_avatar.url
                )
                await msg.edit(embed=done)

                # Step 3: send the file (Discord renders video player automatically)
                file = discord.File(path, filename=os.path.basename(path))
                await interaction.followup.send(file=file)

            except Exception as e:
                await msg.edit(content=f"⚠️ Error: {e}", embed=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Download(bot))

