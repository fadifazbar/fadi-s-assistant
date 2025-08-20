import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import yt_dlp
import datetime

# ---------- YTDL Setup ----------
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # allow playlists now
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ar 48000 -b:a 192k'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


# ---------- YTDL Source ----------
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=not stream)
        )

        if 'entries' in data:  # Playlist
            return [
                cls(discord.FFmpegPCMAudio(entry['url'], **ffmpeg_options), data=entry)
                for entry in data['entries']
            ]
        else:
            return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), data=data)


# ---------- Music Cog ----------
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}      # guild_id -> [songs]
        self.current = {}     # guild_id -> current song
        self.loop_modes = {}  # guild_id -> "off", "one", "all"

        self.afk_check.start()

    # ---------- Helpers ----------
    async def ensure_voice(self, ctx_or_inter):
        if isinstance(ctx_or_inter, commands.Context):
            author = ctx_or_inter.author
        else:
            author = ctx_or_inter.user

        if not author.voice or not author.voice.channel:
            raise commands.CommandError("❌ You must be in a voice channel.")

        vc = ctx_or_inter.guild.voice_client
        if not vc:
            return await author.voice.channel.connect()
        elif vc.channel != author.voice.channel:
            return await vc.move_to(author.voice.channel)
        return vc

    async def play_next(self, guild_id):
        vc = self.bot.get_guild(guild_id).voice_client
        if not vc:
            return

        queue = self.queues.get(guild_id, [])
        loop_mode = self.loop_modes.get(guild_id, "off")

        if loop_mode == "one" and self.current.get(guild_id):
            song = self.current[guild_id]
        elif queue:
            song = queue.pop(0)
            if loop_mode == "all":
                queue.append(song)
        else:
            self.current[guild_id] = None
            await asyncio.sleep(300)  # wait before disconnect if idle
            if not vc.is_playing() and not vc.is_paused():
                await vc.disconnect()
            return

        self.current[guild_id] = song
        vc.play(song, after=lambda e: asyncio.run_coroutine_threadsafe(
            self.play_next(guild_id), self.bot.loop
        ))

        channel = vc.channel.guild.system_channel or vc.channel.guild.text_channels[0]
        asyncio.run_coroutine_threadsafe(
            channel.send(f"🎶 Now playing: **{song.title}**"),
            self.bot.loop
        )

    # ---------- PLAY ----------
    @commands.command(name="play")
    async def play_prefix(self, ctx, *, query: str):
        vc = await self.ensure_voice(ctx)
        async with ctx.typing():
            songs = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
            if not isinstance(songs, list):
                songs = [songs]

            self.queues.setdefault(ctx.guild.id, []).extend(songs)

        if not vc.is_playing():
            await self.play_next(ctx.guild.id)
        await ctx.send(f"🎵 Added {len(songs)} song(s) to the queue.")

    @app_commands.command(name="play", description="Play music from YouTube")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        vc = await self.ensure_voice(interaction)
        songs = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
        if not isinstance(songs, list):
            songs = [songs]

        self.queues.setdefault(interaction.guild.id, []).extend(songs)

        if not vc.is_playing():
            await self.play_next(interaction.guild.id)
        await interaction.followup.send(f"🎵 Added {len(songs)} song(s) to the queue.")

    # ---------- QUEUE ----------
    @commands.command(name="queue")
    async def queue_prefix(self, ctx):
        queue = self.queues.get(ctx.guild.id, [])
        if not queue:
            return await ctx.send("📭 Queue is empty.")
        message = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(queue)])
        await ctx.send(f"📜 **Queue:**\n{message}")

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue_slash(self, interaction: discord.Interaction):
        queue = self.queues.get(interaction.guild.id, [])
        if not queue:
            return await interaction.response.send_message("📭 Queue is empty.")
        message = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(queue)])
        await interaction.response.send_message(f"📜 **Queue:**\n{message}")

    # ---------- NOW PLAYING ----------
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx):
        song = self.current.get(ctx.guild.id)
        if not song:
            return await ctx.send("❌ Nothing is playing.")
        await ctx.send(f"🎶 Now playing: **{song.title}**")

    @app_commands.command(name="nowplaying", description="Show the current playing song")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        song = self.current.get(interaction.guild.id)
        if not song:
            return await interaction.response.send_message("❌ Nothing is playing.")
        await interaction.response.send_message(f"🎶 Now playing: **{song.title}**")

    # ---------- SKIP ----------
    @commands.command(name="skip")
    async def skip_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Skipped.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.")

    # ---------- STOP ----------
    @commands.command(name="stop")
    async def stop_prefix(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            self.queues[ctx.guild.id] = []
            self.current[ctx.guild.id] = None
            await vc.disconnect()
            await ctx.send("🛑 Music stopped, nothing playing.")

    @app_commands.command(name="stop", description="Stop music and disconnect")
    async def stop_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            self.queues[interaction.guild.id] = []
            self.current[interaction.guild.id] = None
            await vc.disconnect()
            await interaction.response.send_message("🛑 Music stopped, nothing playing.")

    # ---------- LOOP ----------
    @commands.command(name="loop")
    async def loop_prefix(self, ctx, mode: str = "off"):
        if mode not in ["off", "one", "all"]:
            return await ctx.send("❌ Loop modes: off, one, all")
        self.loop_modes[ctx.guild.id] = mode
        await ctx.send(f"🔁 Loop mode set to: **{mode}**")

    @app_commands.command(name="loop", description="Set loop mode: off, one, all")
    async def loop_slash(self, interaction: discord.Interaction, mode: str):
        if mode not in ["off", "one", "all"]:
            return await interaction.response.send_message("❌ Loop modes: off, one, all")
        self.loop_modes[interaction.guild.id] = mode
        await interaction.response.send_message(f"🔁 Loop mode set to: **{mode}**")

    # ---------- PAUSE / RESUME ----------
    @commands.command(name="pause")
    async def pause_prefix(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_playing():
            ctx.guild.voice_client.pause()
            await ctx.send("⏸️ Paused.")

    @commands.command(name="resume")
    async def resume_prefix(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_paused():
            ctx.guild.voice_client.resume()
            await ctx.send("▶️ Resumed.")

    @app_commands.command(name="pause", description="Pause the music")
    async def pause_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.")

    @app_commands.command(name="resume", description="Resume the music")
    async def resume_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.")

    # ---------- AFK Disconnect ----------
    @tasks.loop(minutes=1)
    async def afk_check(self):
        for vc in self.bot.voice_clients:
            if not vc.is_playing() and not vc.is_paused():
                if not hasattr(vc, "idle_since"):
                    vc.idle_since = datetime.datetime.utcnow()
                elif (datetime.datetime.utcnow() - vc.idle_since).total_seconds() >= 300:
                    await vc.disconnect()
            else:
                if hasattr(vc, "idle_since"):
                    del vc.idle_since

            if len(vc.channel.members) == 1:
                if not hasattr(vc, "alone_since"):
                    vc.alone_since = datetime.datetime.utcnow()
                elif (datetime.datetime.utcnow() - vc.alone_since).total_seconds() >= 300:
                    await vc.disconnect()
            else:
                if hasattr(vc, "alone_since"):
                    del vc.alone_since


async def setup(bot):
    await bot.add_cog(Music(bot))
