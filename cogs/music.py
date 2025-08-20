import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

# ======================
# YTDL + FFMPEG CONFIG
# ======================
ytdl_format_options = {
    "format": "bestaudio[ext=webm][acodec=opus]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "extract_flat": False,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",  # Force IPv4
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

ffmpeg_options = {"options": "-vn"}


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.data = data
        self.requester = requester

    @classmethod
    async def from_url(cls, url, *, loop=None, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        if "entries" in data:
            data = data["entries"][0]
        filename = data["url"]
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, requester=requester)


# ======================
# MUSIC COG
# ======================
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("❌ You are not connected to a voice channel.")
            return False
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        return True

    # ======================
    # PLAY COMMAND
    # ======================
    @commands.command(name="play")
    async def play(self, ctx, *, search: str):
        if not await self.ensure_voice(ctx):
            return

        async with ctx.typing():
            player = await YTDLSource.from_url(search, loop=self.bot.loop, requester=ctx.author)
            ctx.voice_client.play(
                player,
                after=lambda e: self.bot.loop.create_task(self.play_next(ctx)),
            )
            await ctx.send(f"🎶 Now playing: **{player.data.get('title')}**")

    async def play_next(self, ctx):
        if self.queue:
            next_url, requester = self.queue.pop(0)
            player = await YTDLSource.from_url(next_url, loop=self.bot.loop, requester=requester)
            ctx.voice_client.play(
                player,
                after=lambda e: self.bot.loop.create_task(self.play_next(ctx)),
            )
            await ctx.send(f"🎶 Now playing: **{player.data.get('title')}**")

    # ======================
    # QUEUE COMMAND
    # ======================
    @commands.command(name="queue")
    async def queue_(self, ctx, *, url: str):
        self.queue.append((url, ctx.author))
        await ctx.send(f"✅ Added to queue: **{url}**")

    # ======================
    # SKIP COMMAND
    # ======================
    @commands.command(name="skip")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    # ======================
    # STOP COMMAND
    # ======================
    @commands.command(name="stop")
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("🛑 Stopped and left the channel.")

    # ======================
    # PAUSE COMMAND
    # ======================
    @commands.command(name="pause")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused the music.")
        else:
            await ctx.send("❌ Nothing is playing to pause!")

    # ======================
    # RESUME COMMAND
    # ======================
    @commands.command(name="resume")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed the music.")
        else:
            await ctx.send("❌ Nothing is paused to resume!")

    # ======================
    # SLASH VERSION: PLAY
    # ======================
    @app_commands.command(name="play", description="Play music with a slash command")
    async def slash_play(self, interaction: discord.Interaction, search: str):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ You are not connected to a voice channel.", ephemeral=True)
            return
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()

        player = await YTDLSource.from_url(search, loop=self.bot.loop, requester=interaction.user)
        interaction.guild.voice_client.play(
            player,
            after=lambda e: self.bot.loop.create_task(self.play_next_slash(interaction)),
        )
        await interaction.response.send_message(f"🎶 Now playing: **{player.data.get('title')}**")

    async def play_next_slash(self, interaction):
        if self.queue:
            next_url, requester = self.queue.pop(0)
            player = await YTDLSource.from_url(next_url, loop=self.bot.loop, requester=requester)
            interaction.guild.voice_client.play(
                player,
                after=lambda e: self.bot.loop.create_task(self.play_next_slash(interaction)),
            )
            channel = interaction.channel
            await channel.send(f"🎶 Now playing: **{player.data.get('title')}**")


# Cog setup
async def setup(bot):
    await bot.add_cog(Music(bot))
