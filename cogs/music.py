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
        self.loop = False
        self.current = None

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("❌ You are not connected to a voice channel.")
            return False
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        return True

    # ======================
    # PLAY
    # ======================
    @commands.command(name="play")
    async def play(self, ctx, *, search: str):
        if not await self.ensure_voice(ctx):
            return
        async with ctx.typing():
            player = await YTDLSource.from_url(search, loop=self.bot.loop, requester=ctx.author)
            self.current = player
            ctx.voice_client.play(
                player, after=lambda e: self.bot.loop.create_task(self.play_next(ctx))
            )
            await ctx.send(f"🎶 Now playing: **{player.data.get('title')}** (requested by {ctx.author.mention})")

    @app_commands.command(name="play", description="Play music in your channel")
    async def slash_play(self, interaction: discord.Interaction, search: str):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ You are not in a voice channel.", ephemeral=True)
            return
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        player = await YTDLSource.from_url(search, loop=self.bot.loop, requester=interaction.user)
        self.current = player
        interaction.guild.voice_client.play(
            player, after=lambda e: self.bot.loop.create_task(self.play_next_slash(interaction))
        )
        await interaction.response.send_message(
            f"🎶 Now playing: **{player.data.get('title')}** (requested by {interaction.user.mention})"
        )

    async def play_next(self, ctx):
        if self.loop and self.current:
            ctx.voice_client.play(
                self.current, after=lambda e: self.bot.loop.create_task(self.play_next(ctx))
            )
            await ctx.send(f"🔁 Looping: **{self.current.data.get('title')}**")
            return

        if self.queue:
            next_url, requester = self.queue.pop(0)
            player = await YTDLSource.from_url(next_url, loop=self.bot.loop, requester=requester)
            self.current = player
            ctx.voice_client.play(
                player, after=lambda e: self.bot.loop.create_task(self.play_next(ctx))
            )
            await ctx.send(f"🎶 Now playing: **{player.data.get('title')}** (requested by {requester.mention})")

    async def play_next_slash(self, interaction):
        if self.loop and self.current:
            interaction.guild.voice_client.play(
                self.current, after=lambda e: self.bot.loop.create_task(self.play_next_slash(interaction))
            )
            await interaction.channel.send(f"🔁 Looping: **{self.current.data.get('title')}**")
            return

        if self.queue:
            next_url, requester = self.queue.pop(0)
            player = await YTDLSource.from_url(next_url, loop=self.bot.loop, requester=requester)
            self.current = player
            interaction.guild.voice_client.play(
                player, after=lambda e: self.bot.loop.create_task(self.play_next_slash(interaction))
            )
            await interaction.channel.send(f"🎶 Now playing: **{player.data.get('title')}** (requested by {requester.mention})")

    # ======================
    # QUEUE
    # ======================
    @commands.command(name="queue")
    async def queue_(self, ctx, *, url: str):
        self.queue.append((url, ctx.author))
        await ctx.send(f"✅ Added to queue: **{url}** (requested by {ctx.author.mention})")

    @app_commands.command(name="queue", description="Add a song to the queue")
    async def slash_queue(self, interaction: discord.Interaction, url: str):
        self.queue.append((url, interaction.user))
        await interaction.response.send_message(f"✅ Added to queue: **{url}** (requested by {interaction.user.mention})")

    # ======================
    # SKIP
    # ======================
    @commands.command(name="skip")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Skipped the current song.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def slash_skip(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped the current song.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.")

    # ======================
    # STOP
    # ======================
    @commands.command(name="stop")
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            self.queue.clear()
            self.current = None
            await ctx.send("🛑 Stopped and left the channel.")

    @app_commands.command(name="stop", description="Stop music and disconnect")
    async def slash_stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.queue.clear()
            self.current = None
            await interaction.response.send_message("🛑 Stopped and left the channel.")
        else:
            await interaction.response.send_message("❌ Bot is not in a voice channel.")

    # ======================
    # PAUSE
    # ======================
    @commands.command(name="pause")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused the music.")
        else:
            await ctx.send("❌ Nothing is playing to pause!")

    @app_commands.command(name="pause", description="Pause the current song")
    async def slash_pause(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused the music.")
        else:
            await interaction.response.send_message("❌ Nothing is playing to pause!")

    # ======================
    # RESUME
    # ======================
    @commands.command(name="resume")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed the music.")
        else:
            await ctx.send("❌ Nothing is paused to resume!")

    @app_commands.command(name="resume", description="Resume paused music")
    async def slash_resume(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed the music.")
        else:
            await interaction.response.send_message("❌ Nothing is paused to resume!")

    # ======================
    # NOW PLAYING
    # ======================
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_playing():
            await ctx.send(f"🎶 Now playing: **{vc.source.data.get('title')}** (requested by {vc.source.requester.mention})")
        else:
            await ctx.send("❌ Nothing is playing right now.")

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            await interaction.response.send_message(
                f"🎶 Now playing: **{vc.source.data.get('title')}** (requested by {vc.source.requester.mention})"
            )
        else:
            await interaction.response.send_message("❌ Nothing is playing right now.")

    # ======================
    # LOOP TOGGLE
    # ======================
    @commands.command(name="loop")
    async def loop_(self, ctx):
        self.loop = not self.loop
        await ctx.send(f"🔁 Loop is now **{'enabled' if self.loop else 'disabled'}**.")

    @app_commands.command(name="loop", description="Toggle looping of the current song")
    async def slash_loop(self, interaction: discord.Interaction):
        self.loop = not self.loop
        await interaction.response.send_message(f"🔁 Loop is now **{'enabled' if self.loop else 'disabled'}**.")


# Cog setup
async def setup(bot):
    await bot.add_cog(Music(bot)) 
