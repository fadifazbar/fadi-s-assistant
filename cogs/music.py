import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import yt_dlp
import functools
import itertools
import time

# ---------- YTDL Setup ----------
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(id)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": False,   # allow playlists
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
ffmpeg_options = {"options": "-vn -ar 48000 -b:a 192k"}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, requester, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.url = data.get("url")
        self.webpage_url = data.get("webpage_url")
        self.thumbnail = data.get("thumbnail")
        self.requester = requester

    @classmethod
    async def from_url(cls, url, *, loop, requester, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if "entries" in data:
            # Playlist: grab all entries
            entries = data["entries"]
            return [
                cls(discord.FFmpegPCMAudio(e["url"], **ffmpeg_options), data=e, requester=requester)
                for e in entries if e
            ]
        else:
            return [
                cls(discord.FFmpegPCMAudio(data["url"], **ffmpeg_options), data=data, requester=requester)
            ]


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # guild.id -> [songs]
        self.current = {}  # guild.id -> current song
        self.loop_mode = {}  # guild.id -> "off" / "one" / "all"
        self.idle_timers = {}  # guild.id -> last active time
        self.afk_checker.start()

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    def set_idle(self, guild_id):
        self.idle_timers[guild_id] = time.time()

    # ---------- VOICE ----------
    async def ensure_voice(self, ctx_or_inter):
        if isinstance(ctx_or_inter, commands.Context):
            channel = ctx_or_inter.author.voice.channel if ctx_or_inter.author.voice else None
        else:
            channel = ctx_or_inter.user.voice.channel if ctx_or_inter.user.voice else None

        if not channel:
            raise commands.CommandError("❌ You are not in a voice channel.")

        if ctx_or_inter.guild.voice_client is None:
            await channel.connect()
        elif ctx_or_inter.guild.voice_client.channel != channel:
            await ctx_or_inter.guild.voice_client.move_to(channel)

        self.set_idle(ctx_or_inter.guild.id)

    # ---------- PLAY ----------
    async def start_playing(self, ctx_or_inter, guild, first=False):
        vc = guild.voice_client
        queue = self.get_queue(guild.id)

        if not vc or vc.is_playing() or not queue:
            return

        song = queue[0]
        self.current[guild.id] = song

        def after_play(err):
            if err:
                print(f"Error: {err}")
            self.bot.loop.call_soon_threadsafe(asyncio.create_task, self.after_song(guild))

        vc.play(song, after=after_play)

        # Announce now playing
        embed = discord.Embed(title="🎶 Now Playing", description=f"**{song.title}**", color=discord.Color.green())
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        embed.add_field(name="Requested by", value=song.requester.mention, inline=True)
        if song.webpage_url:
            embed.add_field(name="Link", value=song.webpage_url, inline=True)

        if isinstance(ctx_or_inter, commands.Context):
            await ctx_or_inter.send(embed=embed)
        else:
            await ctx_or_inter.followup.send(embed=embed)

        self.set_idle(guild.id)

    async def after_song(self, guild):
        queue = self.get_queue(guild.id)
        if not queue:
            return

        loop_mode = self.loop_mode.get(guild.id, "off")

        if loop_mode == "one":
            # replay current song
            await self.start_playing(None, guild)
        elif loop_mode == "all":
            song = queue.pop(0)
            queue.append(song)
            await self.start_playing(None, guild)
        else:
            # off
            queue.pop(0)
            if queue:
                await self.start_playing(None, guild)
            else:
                self.current[guild.id] = None

    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx, *, query: str):
        await self.ensure_voice(ctx)
        await ctx.trigger_typing()
        songs = await YTDLSource.from_url(query, loop=self.bot.loop, requester=ctx.author, stream=True)
        queue = self.get_queue(ctx.guild.id)
        queue.extend(songs)
        await ctx.send(f"✅ Added {len(songs)} track(s) to the queue.")
        await self.start_playing(ctx, ctx.guild)

    @app_commands.command(name="play", description="Play music from YouTube or search")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await self.ensure_voice(interaction)
        await interaction.response.defer()
        songs = await YTDLSource.from_url(query, loop=self.bot.loop, requester=interaction.user, stream=True)
        queue = self.get_queue(interaction.guild.id)
        queue.extend(songs)
        await interaction.followup.send(f"✅ Added {len(songs)} track(s) to the queue.")
        await self.start_playing(interaction, interaction.guild)

    # ---------- QUEUE ----------
    @commands.command(name="queue")
    async def queue_cmd(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if not queue:
            await ctx.send("📭 Queue is empty.")
            return
        desc = "\n".join([f"{i+1}. {s.title}" for i, s in enumerate(queue[:10])])
        embed = discord.Embed(title="📜 Queue", description=desc, color=discord.Color.blue())
        await ctx.send(embed=embed)

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue_slash(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue:
            await interaction.response.send_message("📭 Queue is empty.")
            return
        desc = "\n".join([f"{i+1}. {s.title}" for i, s in enumerate(queue[:10])])
        embed = discord.Embed(title="📜 Queue", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

    # ---------- LOOP ----------
    @commands.command(name="loop")
    async def loop_cmd(self, ctx, mode: str = "off"):
        """Modes: off, one, all"""
        if mode not in ["off", "one", "all"]:
            await ctx.send("❌ Invalid mode. Choose `off`, `one`, or `all`.")
            return
        self.loop_mode[ctx.guild.id] = mode
        await ctx.send(f"🔁 Loop mode set to **{mode}**")

    @app_commands.command(name="loop", description="Set loop mode: off, one, all")
    async def loop_slash(self, interaction: discord.Interaction, mode: str):
        if mode not in ["off", "one", "all"]:
            await interaction.response.send_message("❌ Invalid mode. Choose `off`, `one`, or `all`.")
            return
        self.loop_mode[interaction.guild.id] = mode
        await interaction.response.send_message(f"🔁 Loop mode set to **{mode}**")

    # ---------- CONTROLS ----------
    @commands.command(name="skip")
    async def skip_cmd(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_playing():
            ctx.guild.voice_client.stop()
            await ctx.send("⏭️ Skipped.")

    @commands.command(name="pause")
    async def pause_cmd(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_playing():
            ctx.guild.voice_client.pause()
            await ctx.send("⏸️ Paused.")

    @commands.command(name="resume")
    async def resume_cmd(self, ctx):
        if ctx.guild.voice_client and ctx.guild.voice_client.is_paused():
            ctx.guild.voice_client.resume()
            await ctx.send("▶️ Resumed.")

    @commands.command(name="stop")
    async def stop_cmd(self, ctx):
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect()
            self.queues[ctx.guild.id] = []
            self.current[ctx.guild.id] = None
            await ctx.send("🛑 Stopped and disconnected.")

    # ---------- NOW PLAYING ----------
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_cmd(self, ctx):
        song = self.current.get(ctx.guild.id)
        if not song:
            await ctx.send("📭 Nothing is playing.")
            return
        embed = discord.Embed(title="🎶 Now Playing", description=f"**{song.title}**", color=discord.Color.green())
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        await ctx.send(embed=embed)

    # ---------- AFK CHECK ----------
    @tasks.loop(seconds=60)
    async def afk_checker(self):
        for guild in self.bot.guilds:
            vc = guild.voice_client
            if not vc:
                continue
            idle_for = time.time() - self.idle_timers.get(guild.id, time.time())
            if idle_for > 300:  # 5 minutes
                await vc.disconnect()
                self.queues[guild.id] = []
                self.current[guild.id] = None

    @afk_checker.before_loop
    async def before_afk(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Music(bot))
