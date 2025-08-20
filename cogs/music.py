import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import functools

# ---------- YTDL Setup ----------
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # ✅ allow playlists
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'  # ipv6 issues fix
}

ffmpeg_options = {
    'options': '-vn -ar 48000 -b:a 192k'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:  # ✅ playlist
            return [cls(discord.FFmpegPCMAudio(entry['url'], **ffmpeg_options), data=entry)
                    for entry in data['entries'] if entry]
        else:  # ✅ single track
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return [cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)]


# ---------- Music Cog ----------
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.current = None

    async def ensure_voice(self, ctx_or_interaction):
        if isinstance(ctx_or_interaction, commands.Context):
            channel = ctx_or_interaction.author.voice.channel if ctx_or_interaction.author.voice else None
        else:
            channel = ctx_or_interaction.user.voice.channel if ctx_or_interaction.user.voice else None

        if not channel:
            raise commands.CommandError("❌ You are not in a voice channel.")

        if ctx_or_interaction.guild.voice_client is None:
            await channel.connect()
        else:
            if ctx_or_interaction.guild.voice_client.channel != channel:
                await ctx_or_interaction.guild.voice_client.move_to(channel)

    # ---------- Internal: Play Next ----------
    def play_next(self, ctx_or_interaction):
        if self.queue:
            self.current = self.queue.pop(0)
            vc = ctx_or_interaction.guild.voice_client
            vc.play(self.current, after=lambda e: self.play_next(ctx_or_interaction))
        else:
            self.current = None

    # ---------- PLAY ----------
    async def _play(self, ctx_or_interaction, query):
        await self.ensure_voice(ctx_or_interaction)

        loop = self.bot.loop
        players = await YTDLSource.from_url(query, loop=loop, stream=True)

        added_titles = []
        for player in players:
            if ctx_or_interaction.guild.voice_client.is_playing() or self.current:
                self.queue.append(player)
                added_titles.append(player.title)
            else:
                self.current = player
                ctx_or_interaction.guild.voice_client.play(
                    player,
                    after=lambda e: self.play_next(ctx_or_interaction)
                )
                added_titles.append(player.title)

        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(f"🎶 Added to queue: {', '.join(added_titles)}")
        else:
            await ctx_or_interaction.followup.send(f"🎶 Added to queue: {', '.join(added_titles)}")

    @commands.command(name="play")
    async def play_prefix(self, ctx, *, query: str):
        """Play music or playlist from YouTube"""
        async with ctx.typing():
            await self._play(ctx, query)

    @app_commands.command(name="play", description="Play music or playlist from YouTube")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await self._play(interaction, query)

    # ---------- QUEUE ----------
    @commands.command(name="queue")
    async def queue_prefix(self, ctx):
        if not self.queue and not self.current:
            await ctx.send("📭 Queue is empty.")
        else:
            message = f"🎶 Now Playing: **{self.current.title}**\n"
            if self.queue:
                message += "\n".join([f"{i+1}. {track.title}" for i, track in enumerate(self.queue)])
            await ctx.send(message)

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_slash(self, interaction: discord.Interaction):
        if not self.queue and not self.current:
            await interaction.response.send_message("📭 Queue is empty.")
        else:
            message = f"🎶 Now Playing: **{self.current.title}**\n"
            if self.queue:
                message += "\n".join([f"{i+1}. {track.title}" for i, track in enumerate(self.queue)])
            await interaction.response.send_message(message)

    # ---------- NOW PLAYING ----------
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx):
        if self.current:
            await ctx.send(f"🎵 Now playing: **{self.current.title}**")
        else:
            await ctx.send("❌ Nothing is playing right now.")

    @app_commands.command(name="nowplaying", description="Show current song")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        if self.current:
            await interaction.response.send_message(f"🎵 Now playing: **{self.current.title}**")
        else:
            await interaction.response.send_message("❌ Nothing is playing right now.")

    # ---------- STOP ----------
    @commands.command(name="stop")
    async def stop_prefix(self, ctx):
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect()
            self.queue.clear()
            self.current = None
            await ctx.send("🛑 Stopped and disconnected.")

    @app_commands.command(name="stop", description="Stop music and leave VC")
    async def stop_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.queue.clear()
            self.current = None
            await interaction.response.send_message("🛑 Stopped and disconnected.")

    # ---------- SKIP ----------
    @commands.command(name="skip")
    async def skip_prefix(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_playing():
            ctx.guild.voice_client.stop()
            await ctx.send("⏭️ Skipped the current track.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped the current track.")

    # ---------- PAUSE / RESUME ----------
    @commands.command(name="pause")
    async def pause_prefix(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_playing():
            ctx.guild.voice_client.pause()
            await ctx.send("⏸️ Paused.")

    @app_commands.command(name="pause", description="Pause the music")
    async def pause_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.")

    @commands.command(name="resume")
    async def resume_prefix(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_paused():
            ctx.guild.voice_client.resume()
            await ctx.send("▶️ Resumed.")

    @app_commands.command(name="resume", description="Resume the music")
    async def resume_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.")


async def setup(bot):
    await bot.add_cog(Music(bot))
