import discord
from discord.ext import commands
import yt_dlp
import aiohttp
import os
import time

# ---------- CONFIG ----------
EXTERNAL_HOST = "https://files.example.com/upload"  # Replace with your hosting API
MAX_DISCORD_FILESIZE = 8 * 1024 * 1024  # 8MB
# ----------------------------

def sizeof_fmt(num, suffix="B"):
    """Convert bytes → human-readable format."""
    for unit in ["", "K", "M", "G"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}T{suffix}"

async def upload_external(file_path: str):
    """Upload file to external hosting and return link."""
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            data = {"file": f}
            async with session.post(EXTERNAL_HOST, data=data) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    return res.get("url", None)
                return None

class URLDownload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="urldownload")
    async def urldownload(self, ctx, url: str):
        start_time = time.time()

        status_msg = await ctx.send("🔄 Fetching video...")

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": "downloads/%(title).200s.%(ext)s",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            # --- Fetch info ---
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)
                duration_str = time.strftime("%M:%S", time.gmtime(duration))
                quality = info.get("format_note", "unknown")
                filename = ydl.prepare_filename(info)

                await status_msg.edit(content="⬇️ Downloading...")
                ydl.download([url])

            file_size = os.path.getsize(filename)
            elapsed = time.time() - start_time

            # --- Build embed ---
            embed = discord.Embed(
                title="✅ Download Complete",
                color=discord.Color.green()
            )
            embed.add_field(name="📹 Title", value=title, inline=False)
            embed.add_field(name="⏱️ Length", value=duration_str, inline=True)
            embed.add_field(name="📺 Quality", value=quality, inline=True)
            embed.add_field(name="📦 Size", value=sizeof_fmt(file_size), inline=True)
            embed.add_field(name="⏳ Time taken", value=f"{elapsed:.2f}s", inline=True)

            # --- If ≤ 8MB: upload to Discord ---
            if file_size <= MAX_DISCORD_FILESIZE:
                await status_msg.edit(content="📤 Uploading to Discord...")
                await ctx.send(embed=embed, file=discord.File(filename))

            # --- If > 8MB: external hosting ---
            else:
                await status_msg.edit(
                    content=f"⚠️ File too large to fit Discord limits ({sizeof_fmt(file_size)}).\n"
                            f"Auto-compression not possible for this size.\n"
                            f"Using external hosting to download your video"
                )

                link = await upload_external(filename)

                if link:
                    embed.add_field(name="🔗 External Link", value=link, inline=False)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Upload failed. Please try again later.")

        except Exception as e:
            await status_msg.edit(content=f"❌ Download Failed\nError: `{e}`")

        finally:
            if "filename" in locals() and os.path.exists(filename):
                os.remove(filename)

# ---------- Setup ----------
async def setup(bot):
    await bot.add_cog(URLDownload(bot))
