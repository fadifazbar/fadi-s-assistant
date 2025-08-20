import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp

# ---------- YTDL Setup ----------
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # allow playlist support
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
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

        if "entries" in data:  # playlist
            return [await cls.from_url(entry["webpage_url"], loop=loop, stream=stream) for entry in data["entries"]]

        filename = data["url"] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


# ---------- Music Cog ----------
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.current = None

    async def ensure_voice(self, ctx_or_interaction):
        """Make sure bot only plays in one VC per server"""
        if isinstance(ctx_or_interaction, commands.Context):
            author_channel = ctx_or_interaction.author.voice.channel if ctx_or_interaction.author.voice else None
        else:
            author_channel = ctx_or_interaction.user.voice.channel if ctx_or_interaction.user.voice else None

        if not author_channel:
            raise commands.CommandError("❌ You are not in a voice channel.")

        voice_client = ctx_or_interaction.guild.voice_client

        if voice_client is None:
            await author_channel.connect()
        else:
            if voice_client.channel != author_channel:
                raise commands.CommandError(
                    f"❌ I’m already playing music in **{voice_client.channel.name}**."
                )

    def play_next(self, ctx_or_interaction):
        if self.queue:
            self.current = self.queue.pop(0)
            ctx_or_interaction.guild.voice_client.play(
                self.current,
                after=lambda e: self.play_next(ctx_or_interaction) if not e else print(f"Player error: {e}")
            )

    async def add_to_queue(self, ctx_or_interaction, query, stream=True):
        entries = await YTDLSource.from_url(query, loop=self.bot.loop, stream=stream)

        if isinstance(entries, list):  # playlist
            self.queue.extend(entries)
            return f"📃 Added **{len(entries)} tracks** from playlist to the queue."
        else:
            self.queue.append(entries)
            return f"🎵 Added to queue: **{entries.title}**"

    # ---------- PLAY ----------
    @commands.command(name="play")
    async def play_prefix(self, ctx, *, query: str):
        await self.ensure_voice(ctx)
        async with ctx.typing():
            msg = await self.add_to_queue(ctx, query)
            if not ctx.guild.voice_client.is_playing():
                self.play_next(ctx)
        await ctx.send(msg)

    @app_commands.command(name="play", description="Play music from YouTube or add to queue")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await self.ensure_voice(interaction)
        await interaction.response.defer()
        msg = await self.add_to_queue(interaction, query)
        if not interaction.guild.voice_client.is_playing():
            self.play_next(interaction)
        await interaction.followup.send(msg)

    # ---------- QUEUE ----------
    @commands.command(name="queue")
    async def queue_prefix(self, ctx):
        if not self.queue:
            await ctx.send("📭 Queue is empty.")
        else:
            queue_list = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(self.queue)])
            await ctx.send(f"📜 Current Queue:\n{queue_list}")

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue_slash(self, interaction: discord.Interaction):
        if not self.queue:
            await interaction.response.send_message("📭 Queue is empty.")
        else:
            queue_list = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(self.queue)])
            await interaction.response.send_message(f"📜 Current Queue:\n{queue_list}")

    # ---------- STOP ----------
    @commands.command(name="stop")
    async def stop_prefix(self, ctx):
        if ctx.guild.voice_client:
            self.queue.clear()
            await ctx.guild.voice_client.disconnect()
            await ctx.send("🛑 Stopped and disconnected.")

    @app_commands.command(name="stop", description="Stop music and leave VC")
    async def stop_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            self.queue.clear()
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("🛑 Stopped and disconnected.")

    # ---------- SKIP ----------
    @commands.command(name="skip")
    async def skip_prefix(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_playing():
            ctx.guild.voice_client.stop()
            await ctx.send("⏭️ Skipped.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped.")

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
