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
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
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

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


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

    # ---------- PLAY ----------
    @commands.command(name="play")
    async def play_prefix(self, ctx, *, query: str):
        """Play music from YouTube"""
        await self.ensure_voice(ctx)
        async with ctx.typing():
            player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
            ctx.guild.voice_client.play(player, after=lambda e: print(f"Player error: {e}") if e else None)
        await ctx.send(f"🎶 Now playing: **{player.title}**")

    @app_commands.command(name="play", description="Play music from YouTube")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await self.ensure_voice(interaction)
        await interaction.response.defer()
        player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
        interaction.guild.voice_client.play(player, after=lambda e: print(f"Player error: {e}") if e else None)
        await interaction.followup.send(f"🎶 Now playing: **{player.title}**")

    # ---------- STOP ----------
    @commands.command(name="stop")
    async def stop_prefix(self, ctx):
        """Stop music and leave VC"""
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect()
            await ctx.send("🛑 Stopped and disconnected.")

    @app_commands.command(name="stop", description="Stop music and leave VC")
    async def stop_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("🛑 Stopped and disconnected.")

    # ---------- SKIP ----------
    @commands.command(name="skip")
    async def skip_prefix(self, ctx):
        """Skip the current song"""
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
