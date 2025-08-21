import os
import time
import math
import asyncio
import discord
import yt_dlp as youtube_dl
import subprocess
import uuid

# ───────────────────────────────────────────────
# Progress Hook Class
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
# Helper Functions
# ───────────────────────────────────────────────
def get_discord_limit(guild):
    if guild.premium_tier == 0:
        return 8
    elif guild.premium_tier == 1:
        return 50
    elif guild.premium_tier == 2:
        return 100
    else:
        return 500

def compress_video(input_path, output_path, target_mb):
    """Compress with ffmpeg to fit under target size (MB)."""
    try:
        size_bytes = os.path.getsize(input_path)
        target_bitrate = (target_mb * 8 * 1024 * 1024) / (os.path.getsize(input_path) / (1024 * 1024))

        command = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-b:v", f"{int(target_bitrate)}k",
            "-bufsize", f"{int(target_bitrate)}k",
            "-maxrate", f"{int(target_bitrate)}k",
            output_path
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return os.path.exists(output_path)
    except Exception as e:
        print(f"[Compression Error] {e}")
        return False

# Placeholder external upload (replace with your file host logic)
def upload_external(file_path):
    fake_url = f"https://files.example.com/{uuid.uuid4().hex}.mp4"
    return fake_url

# ───────────────────────────────────────────────
# Main download function
# ───────────────────────────────────────────────
async def download_video(ctx, url, output_path):
    start_time = time.time()

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
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        elapsed = time.time() - start_time

        guild = ctx.guild
        limit = get_discord_limit(guild)

        final = discord.Embed(
            title="✅ Download Complete",
            description=f"**{title}**",
            color=discord.Color.green()
        )
        final.add_field(name="Video Length", value=f"{math.floor(duration/60)}m {duration%60:.0f}s", inline=True)
        final.add_field(name="Quality", value=quality, inline=True)
        final.add_field(name="Download Time", value=f"{elapsed:.1f} sec", inline=True)

        # If fits within Discord limit
        if file_size <= limit:
            final.set_footer(text=f"File Size: {file_size:.2f} MB (Under {limit} MB limit)")
            await msg.edit(embed=final)
            await ctx.send(file=discord.File(file_path))
        else:
            # Try compression
            compressed_path = output_path.replace(".mp4", "_compressed.mp4")
            success = compress_video(file_path, compressed_path, limit)

            if success:
                compressed_size = os.path.getsize(compressed_path) / (1024 * 1024)
                if compressed_size <= limit:
                    final.title = "✅ Download Compressed & Complete"
                    final.set_footer(text=f"Compressed File Size: {compressed_size:.2f} MB (Under {limit} MB limit)")
                    await msg.edit(embed=final)
                    await ctx.send(file=discord.File(compressed_path))
                    return

            # Upload to external if still too big
            external_link = upload_external(file_path)
            final.title = "⚠️ File Too Large for Discord"
            final.description += f"\nFile size: **{file_size:.2f} MB**\nServer limit: **{limit} MB**"
            final.add_field(name="Download Link", value=external_link, inline=False)
            final.color = discord.Color.orange()
            await msg.edit(embed=final)

    except Exception as e:
        error = discord.Embed(
            title="❌ Download Failed",
            description=f"Error: {str(e)}",
            color=discord.Color.red()
        )
        await msg.edit(embed=error)
