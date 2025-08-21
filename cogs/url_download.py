import os
import time
import math
import asyncio
import discord
import yt_dlp as youtube_dl

# ───────────────────────────────────────────────
# Progress Hook
# ───────────────────────────────────────────────
class YTDLLogger:
    def __init__(self, message):
        self.message = message
        self.start_time = time.time()
        self.last_update = 0
        self.embed = discord.Embed(
            title="🔄 Fetching Video Info...",
            description="Please wait...",
            color=discord.Color.blurple()
        )

    async def update_message(self, ctx):
        try:
            await self.message.edit(embed=self.embed)
        except Exception:
            pass

    async def hook(self, d):
        status = d['status']
        now = time.time()

        # Only update every 2 sec to prevent rate limit spam
        if now - self.last_update < 2 and status == "downloading":
            return

        self.last_update = now

        if status == 'downloading':
            percent = d.get('_percent_str', '0.0%').strip()
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')

            try:
                p = float(percent.replace('%', ''))
            except:
                p = 0.0

            # Progress bar
            blocks = int(p // 10)
            bar = "🟩" * blocks + "⬛" * (10 - blocks)

            self.embed.title = "⬇️ Downloading Video..."
            self.embed.description = f"""
**Progress:** {percent}/100%
{bar}

**Speed:** {speed}
**ETA:** {eta}
            """

        elif status == 'finished':
            self.embed.title = "📦 Finalizing..."
            self.embed.description = "Merging audio + video..."

        await self.update_message(d['ctx'])

# ───────────────────────────────────────────────
# Main download function
# ───────────────────────────────────────────────
async def download_video(ctx, url, output_path, max_filesize):
    start_time = time.time()

    # Initial embed
    embed = discord.Embed(
        title="🔄 Fetching Video Info...",
        description="Please wait...",
        color=discord.Color.blurple()
    )
    msg = await ctx.send(embed=embed)

    logger = YTDLLogger(msg)

    ydl_opts = {
        "outtmpl": output_path,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "progress_hooks": [logger.hook],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        def _download():
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _download)
        duration = info.get("duration", 0)
        quality = info.get("format", "unknown")
        title = info.get("title", "Unknown Title")

        file_path = ydl_opts["outtmpl"]
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        elapsed = time.time() - start_time

        # Build final embed
        final = discord.Embed(
            title="✅ Download Complete",
            description=f"**{title}**",
            color=discord.Color.green()
        )
        final.add_field(name="Video Length", value=f"{math.floor(duration/60)}m {duration%60:.0f}s", inline=True)
        final.add_field(name="Quality", value=quality, inline=True)
        final.add_field(name="Download Time", value=f"{elapsed:.1f} sec", inline=True)

        # Nitro-based limits
        guild = ctx.guild
        if guild.premium_tier == 0:
            limit = 8
        elif guild.premium_tier == 1:
            limit = 50
        elif guild.premium_tier == 2:
            limit = 100
        else:
            limit = 500

        if file_size <= limit:
            final.set_footer(text=f"File Size: {file_size:.2f} MB (Under Discord limit: {limit} MB)")
            await msg.edit(embed=final)
            await ctx.send(file=discord.File(file_path))
        else:
            final.title = "⚠️ File Too Large for Discord"
            final.description += f"\nFile size: **{file_size:.2f} MB**\nServer limit: **{limit} MB**"
            final.color = discord.Color.orange()
            await msg.edit(embed=final)

    except Exception as e:
        error = discord.Embed(
            title="❌ Download Failed",
            description=f"Error: {str(e)}",
            color=discord.Color.red()
        )
        await msg.edit(embed=error)
