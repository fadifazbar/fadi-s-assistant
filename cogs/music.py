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
    'noplaylist': False,  # allow playlists
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


# ---------- YTDL Wrapper ----------
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5, requester=None):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.requester = requester

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:  # Playlist support
            return [await cls.from_url(entry['url'], loop=loop, stream=stream, requester=requester)
                    for entry in data['entries']]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, requester=requester)


# ---------- Music Cog ----------
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.current = None
        self.loop_mode = "off"  # off, one, all
        self.afk_timer = {}  # guild.id -> last idle time

        # Start AFK check loop
        self.bot.loop.create_task(self.afk_check())

    # ---------- AFK CHECK ----------
    async def afk_check(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = asyncio.get_event_loop().time()
            for guild in self.bot.guilds:
                vc = guild.voice_client
                if vc and not vc.is_playing() and not vc.is_paused():
                    last_idle = self.afk_timer.get(guild.id, None)
                    if last_idle and now - last_idle > 300:  # 5 mins
                        await vc.disconnect()
                        try:
                            await guild.system_channel.send("👋 Left VC after 5 minutes of inactivity.")
                        except:
                            pass
            await asyncio.sleep(60)

    # ---------- Ensure in VC ----------
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

    # ---------- Play Next ----------
    def play_next(self, ctx_or_interaction):
        if self.loop_mode == "one" and self.current:
            self.queue.insert(0, self.current)
        elif self.loop_mode == "all" and self.current:
            self.queue.append(self.current)

        if self.queue:
            self.current = self.queue.pop(0)
            ctx_or_interaction.guild.voice_client.play(
                self.current,
                after=lambda e: self.play_next(ctx_or_interaction) if not e else print(f"Player error: {e}")
            )
            coro = ctx_or_interaction.channel.send(f"🎶 Now playing: **{self.current.title}**")
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
        else:
            self.current = None
            self.afk_timer[ctx_or_interaction.guild.id] = asyncio.get_event_loop().time()
            coro = ctx_or_interaction.channel.send("🛑 Music stopped, nothing playing.")
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    # ---------- Add to Queue ----------
    async def add_to_queue(self, query, ctx_or_interaction, requester=None):
        entries = await YTDLSource.from_url(query, loop=self.bot.loop, stream=False, requester=requester)
        if isinstance(entries, list):  # Playlist
            self.queue.extend(entries)
            await ctx_or_interaction.send(f"📃 Added {len(entries)} tracks from playlist to the queue.")
        else:
            self.queue.append(entries)
            await ctx_or_interaction.send(f"🎵 Added to queue: **{entries.title}**")

    # ---------- PLAY ----------
    @commands.command(name="play")
    async def play_prefix(self, ctx, *, query: str):
        await self.ensure_voice(ctx)
        await self.add_to_queue(query, ctx, requester=ctx.author)

        if not ctx.guild.voice_client.is_playing():
            self.play_next(ctx)

    @app_commands.command(name="play", description="Play music from YouTube or playlist")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await self.ensure_voice(interaction)
        await interaction.response.defer()
        await self.add_to_queue(query, interaction, requester=interaction.user)

        if not interaction.guild.voice_client.is_playing():
            self.play_next(interaction)

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
            if self.loop_mode == "all" and self.current:
                self.queue.append(self.current)
            ctx.guild.voice_client.stop()
            await ctx.send("⏭️ Skipped the current track.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip_slash(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            if self.loop_mode == "all" and self.current:
                self.queue.append(self.current)
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped the current track.")

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

    # ---------- NOW PLAYING ----------
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx):
        if self.current:
            await ctx.send(f"🎶 Now playing: **{self.current.title}** (requested by {self.current.requester.mention})")
        else:
            await ctx.send("❌ Nothing is currently playing.")

    @app_commands.command(name="nowplaying", description="Show the current song")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        if self.current:
            await interaction.response.send_message(
                f"🎶 Now playing: **{self.current.title}** (requested by {self.current.requester.mention})")
        else:
            await interaction.response.send_message("❌ Nothing is currently playing.")

    # ---------- QUEUE ----------
    @commands.command(name="queue")
    async def queue_prefix(self, ctx):
        if not self.queue:
            await ctx.send("📭 The queue is empty.")
        else:
            msg = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(self.queue[:10])])
            await ctx.send(f"📃 **Queue:**\n{msg}")

    @app_commands.command(name="queue", description="Show the queue")
    async def queue_slash(self, interaction: discord.Interaction):
        if not self.queue:
            await interaction.response.send_message("📭 The queue is empty.")
        else:
            msg = "\n".join([f"{i+1}. {song.title}" for i, song in enumerate(self.queue[:10])])
            await interaction.response.send_message(f"📃 **Queue:**\n{msg}")

    # ---------- LOOP ----------
    @commands.command(name="loop")
    async def loop_prefix(self, ctx, mode: str = "off"):
        if mode not in ["off", "one", "all"]:
            return await ctx.send("❌ Invalid loop mode. Use: off, one, all")

        self.loop_mode = mode
        await ctx.send(f"🔁 Loop mode set to **{mode}**")

    @app_commands.command(name="loop", description="Set loop mode (off, one, all)")
    async def loop_slash(self, interaction: discord.Interaction, mode: str):
        if mode not in ["off", "one", "all"]:
            return await interaction.response.send_message("❌ Invalid loop mode. Use: off, one, all")

        self.loop_mode = mode
        await interaction.response.send_message(f"🔁 Loop mode set to **{mode}**")


async def setup(bot):
    await bot.add_cog(Music(bot))
