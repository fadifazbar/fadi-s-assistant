import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp as youtube_dl
import time
from collections import deque

class Track:
    def __init__(self, source, title, url, requester, thumbnail=None):
        self.source = source
        self.title = title
        self.url = url
        self.requester = requester
        self.thumbnail = thumbnail


class MusicPlayer:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue = deque()
        self.current: Track | None = None
        self.voice_client: discord.VoiceClient | None = None
        self.loop_mode = "off"  # off, one, all
        self._task = bot.loop.create_task(self.player_loop())
        self._wake = asyncio.Event()
        self._alone_since = None
        self._idle_since = None

    def is_connected(self):
        return self.voice_client and self.voice_client.is_connected()

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    def enqueue(self, tracks):
        self.queue.extend(tracks)
        self._wake.set()

    async def _disconnect_if_idle(self):
        """Disconnect if idle or alone for >5 minutes."""
        if self.voice_client and not self.is_playing() and not self.queue:
            if self._idle_since is None:
                self._idle_since = time.time()
            elif time.time() - self._idle_since > 300:  # 5 min
                await self.voice_client.disconnect()
                self._idle_since = None
                return
        else:
            self._idle_since = None

        if self.voice_client and self.is_alone():
            if self._alone_since is None:
                self._alone_since = time.time()
            elif time.time() - self._alone_since > 300:  # 5 min alone
                await self.voice_client.disconnect()
                self._alone_since = None
                return
        else:
            self._alone_since = None

    def is_alone(self):
        if not self.voice_client or not self.voice_client.channel:
            return False
        members = [m for m in self.voice_client.channel.members if not m.bot]
        return len(members) == 0

    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self._wake.wait()
            self._wake.clear()

            if not self.queue and self.loop_mode != "one":
                self.current = None
                await self._disconnect_if_idle()
                continue

            if self.loop_mode == "one" and self.current:
                track = self.current
            else:
                if not self.queue:
                    continue
                track = self.queue.popleft()

            self.current = track

            if not self.voice_client:
                continue

            self.voice_client.play(track.source, after=lambda _: self._wake.set())

            try:
                # "Now Playing" Embed
                embed = discord.Embed(
                    title="🎶 Now Playing",
                    description=f"**[{track.title}]({track.url})**",
                    color=discord.Color.green()
                )
                if track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
                embed.add_field(name="Requested by", value=track.requester.mention)
                channel = await self._get_text_channel()
                if channel:
                    await channel.send(embed=embed)
            except Exception:
                pass

            while self.voice_client.is_playing() or self.voice_client.is_paused():
                await asyncio.sleep(2)

            # Handle looping
            finished = self.current
            self.current = None

            if self.loop_mode == "one":
                self.queue.appendleft(finished)
            elif self.loop_mode == "all":
                self.queue.append(finished)

                # 🔁 Playlist loop message
                if not self.queue:  # just in case
                    continue
                if len(self.queue) == 1:  # when finishing last song
                    channel = await self._get_text_channel()
                    if channel:
                        loop_embed = discord.Embed(
                            title="🔁 Playlist Looped",
                            description="The playlist has finished and is starting again!",
                            color=discord.Color.blurple()
                        )
                        await channel.send(embed=loop_embed)

            self._wake.set()

    async def _get_text_channel(self):
        """Find a text channel to send messages (priority: system_channel > first text channel)."""
        if self.guild.system_channel:
            return self.guild.system_channel
        for c in self.guild.text_channels:
            if c.permissions_for(self.guild.me).send_messages:
                return c
        return None


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}

    def player(self, guild: discord.Guild):
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self.bot, guild)
        return self.players[guild.id]

    async def _connect_to_invoker(self, ctx_or_inter):
        if isinstance(ctx_or_inter, commands.Context):
            author = ctx_or_inter.author
            guild = ctx_or_inter.guild
        else:
            author = ctx_or_inter.user
            guild = ctx_or_inter.guild

        vc = author.voice.channel if author.voice else None
        if not vc:
            if isinstance(ctx_or_inter, commands.Context):
                await ctx_or_inter.reply("❌ You must be in a voice channel.")
            else:
                await ctx_or_inter.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
            return None

        player = self.player(guild)
        if not player.voice_client or not player.is_connected():
            player.voice_client = await vc.connect()
        return player

    async def _extract_tracks(self, query, requester):
        opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": False,
        }
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: youtube_dl.YoutubeDL(opts).extract_info(query, download=False))
        tracks = []
        if "entries" in data:
            for e in data["entries"]:
                src = await discord.FFmpegOpusAudio.from_probe(e["url"])
                tracks.append(Track(src, e.get("title"), e.get("webpage_url"), requester, e.get("thumbnail")))
        else:
            src = await discord.FFmpegOpusAudio.from_probe(data["url"])
            tracks.append(Track(src, data.get("title"), data.get("webpage_url"), requester, data.get("thumbnail")))
        return tracks

    # === Commands ===

    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx, *, query: str):
        await ctx.trigger_typing()
        pl = await self._connect_to_invoker(ctx)
        if not pl:
            return
        tracks = await self._extract_tracks(query, ctx.author)
        if not tracks:
            return await ctx.reply("❌ Couldn't find anything.")
        pl.enqueue(tracks)
        await ctx.reply(f"✅ Added **{len(tracks)}** track(s).")

    @app_commands.command(name="play", description="Play music")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        pl = await self._connect_to_invoker(interaction)
        if not pl:
            return
        tracks = await self._extract_tracks(query, interaction.user)
        if not tracks:
            return await interaction.followup.send("❌ Couldn't find anything.")
        pl.enqueue(tracks)
        await interaction.followup.send(f"✅ Added **{len(tracks)}** track(s).")

    @commands.command(name="loop")
    async def loop_prefix(self, ctx: commands.Context, mode: str = "off"):
        mode = mode.lower()
        if mode not in {"off", "one", "all"}:
            return await ctx.reply("❌ Choose `off`, `one`, or `all`.")
        self.player(ctx.guild).loop_mode = mode
        await ctx.reply(f"🔁 Loop mode set to **{mode}**")

    @app_commands.command(name="loop", description="Set loop mode")
    @app_commands.choices(mode=[
        app_commands.Choice(name="off", value="off"),
        app_commands.Choice(name="one", value="one"),
        app_commands.Choice(name="all", value="all"),
    ])
    async def loop_slash(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        self.player(interaction.guild).loop_mode = mode.value
        await interaction.response.send_message(f"🔁 Loop mode set to **{mode.value}**")

async def setup(bot):
    await bot.add_cog(Music(bot))
