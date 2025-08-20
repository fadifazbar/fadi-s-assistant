import asyncio
import re
from dataclasses import dataclass
from typing import Optional, Deque, List
from collections import deque

import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": False,                 # allow playlists (we’ll filter per-command)
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    # Make HLS/frag streams more reliable:
    "extract_flat": False,
    "cachedir": False,
    "geo_bypass": True,
    "nocheckcertificate": True,
}

FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn -ar 48000 -ac 2 -loglevel warning"

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

YOUTUBE_PLAYLIST_RE = re.compile(r"(?:list=)([A-Za-z0-9_-]+)")
YOUTUBE_URL_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+")


@dataclass
class Track:
    title: str
    stream_url: str          # direct audio URL for ffmpeg
    webpage_url: str         # youtube page (for display)
    duration: Optional[int]  # seconds
    requester: discord.User
    thumbnail: Optional[str] = None


class MusicPlayer:
    """Per-guild player loop with queue + looping + auto-disconnect."""
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue: Deque[Track] = deque()
        self.current: Optional[Track] = None
        self.next_event = asyncio.Event()
        self.loop_mode: str = "off"      # 'off' | 'one' | 'all'
        self.text_channel: Optional[discord.TextChannel] = None
        self.volume: float = 0.5

        # idle / alone timers
        self._idle_since: Optional[float] = None
        self._alone_since: Optional[float] = None

        self.task: Optional[asyncio.Task] = None

    # ---------- Helpers ----------
    def voice(self) -> Optional[discord.VoiceClient]:
        return self.guild.voice_client

    def is_playing(self) -> bool:
        vc = self.voice()
        return bool(vc and vc.is_playing())

    def mark_activity(self):
        self._idle_since = None  # reset idle timer on any activity

    def set_idle(self):
        if self._idle_since is None:
            self._idle_since = asyncio.get_event_loop().time()

    def set_alone(self, alone: bool):
        if alone:
            if self._alone_since is None:
                self._alone_since = asyncio.get_event_loop().time()
        else:
            self._alone_since = None

    async def send(self, content=None, **kwargs):
        if self.text_channel:
            try:
                return await self.text_channel.send(content, **kwargs)
            except discord.HTTPException:
                pass

    # ---------- Public API ----------
    async def ensure_connected(self, channel: discord.VoiceChannel):
        vc = self.voice()
        if vc is None:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)
        # set initial alone state
        self.set_alone(self._is_alone())
        self.mark_activity()

    def enqueue(self, tracks: List[Track]):
        for t in tracks:
            self.queue.append(t)
        self.mark_activity()
        # start loop if not running
        if self.task is None or self.task.done():
            self.task = self.bot.loop.create_task(self._player_loop())

    # ---------- Core loop ----------
    async def _player_loop(self):
        """Single loop that decides what to play next; prevents spam/duplicates."""
        await asyncio.sleep(0)  # yield
        sent_stopped = False

        while True:
            # check disconnect conditions periodically
            await self._auto_disconnect_check()

            # pick next track
            if self.current is None:
                if not self.queue:
                    if not sent_stopped:
                        await self.send("🛑 Music stopped, nothing playing.")
                        sent_stopped = True
                        self.set_idle()  # start idle timer
                    # wait for something to arrive or disconnect
                    try:
                        await asyncio.wait_for(self.next_event.wait(), timeout=15.0)
                    except asyncio.TimeoutError:
                        continue
                    finally:
                        self.next_event.clear()
                    continue

                # got a track
                sent_stopped = False
                self.current = self.queue[0]  # peek; pop after we start
                self.mark_activity()

                # If loop_all is active and we just popped, we’ll re-append later.
                # If loop_one, we keep current as-is.

                try:
                    source = discord.FFmpegPCMAudio(
                        self.current.stream_url,
                        before_options=FFMPEG_BEFORE,
                        options=FFMPEG_OPTS
                    )
                    source = discord.PCMVolumeTransformer(source, volume=self.volume)
                except Exception as e:
                    await self.send(f"⚠️ Failed to create player for **{self.current.title}**: `{e}`")
                    # drop the bad track
                    try:
                        self.queue.popleft()
                    except IndexError:
                        pass
                    self.current = None
                    continue

                vc = self.voice()
                if not vc:
                    # voice missing (disconnected?), bail
                    self.current = None
                    await asyncio.sleep(1)
                    continue

                # start playback
                started = asyncio.Event()

                def _after(err):
                    # Schedule setting event in the main loop thread-safely
                    if err:
                        print(f"[MusicPlayer] after error: {err}")
                    self.bot.loop.call_soon_threadsafe(started.set)

                vc.play(source, after=_after)

                # announce only once per track
                await self.send(f"🎶 Now playing: **{self.current.title}**")
                self.mark_activity()

                # We popped after we’ve definitely started:
                # (so queue shows the "up next" correctly while buffer starts)
                try:
                    self.queue.popleft()
                except IndexError:
                    pass

                # Wait for the track to finish
                await started.wait()

                # When finished:
                # Re-queue rules
                if self.loop_mode == "one" and self.current:
                    # put it back to the front to play again immediately
                    self.queue.appendleft(self.current)
                elif self.loop_mode == "all" and self.current:
                    # put it at the end to cycle playlist
                    self.queue.append(self.current)

                self.current = None
                self.set_idle()
                self.next_event.set()  # in case something is waiting
                continue

            await asyncio.sleep(0.05)

    async def _auto_disconnect_check(self):
        """Check 'alone in VC' and 'idle' for 5 minutes."""
        vc = self.voice()
        if not vc or not vc.channel:
            return

        # Alone check
        alone = self._is_alone()
        self.set_alone(alone)

        now = asyncio.get_event_loop().time()

        # Alone for 5 minutes
        if self._alone_since and (now - self._alone_since) >= 300:
            await self.send("👋 I’ve been alone for 5 minutes, disconnecting.")
            await self._disconnect_cleanup()
            return

        # Idle (no current, queue empty) for 5 minutes
        if self._idle_since and (now - self._idle_since) >= 300:
            await self.send("⏱️ No music for 5 minutes, disconnecting.")
            await self._disconnect_cleanup()
            return

    def _is_alone(self) -> bool:
        vc = self.voice()
        if not vc or not vc.channel:
            return False
        members = [m for m in vc.channel.members if not m.bot]
        return len(members) == 0

    async def _disconnect_cleanup(self):
        vc = self.voice()
        if vc:
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass
        self.queue.clear()
        self.current = None
        self._idle_since = None
        self._alone_since = None
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None

    # ---------- External triggers ----------
    def notify_new_tracks(self):
        """Wake the loop to notice new tracks."""
        self.next_event.set()


# ---------------- Cog ----------------
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}  # guild.id -> player

    # Utility: get/create player
    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        p = self.players.get(guild.id)
        if p is None:
            p = MusicPlayer(self.bot, guild)
            self.players[guild.id] = p
        return p

    # ---------- YTDL helpers ----------
    async def _yt_search_or_url(self, query: str, requester: discord.User, for_playlist: bool):
        """
        Returns a list[Track]. Supports:
        - plain search ("fnaf 1 song")
        - video URL
        - playlist URL
        """
        loop = asyncio.get_running_loop()

        def extract():
            # If playlist URL and allowed, don't force noplaylist
            opts = YTDL_OPTS.copy()
            opts["noplaylist"] = not for_playlist and not YOUTUBE_PLAYLIST_RE.search(query)
            with yt_dlp.YoutubeDL(opts) as y:
                return y.extract_info(query, download=False)

        data = await loop.run_in_executor(None, extract)

        tracks: List[Track] = []

        if data is None:
            return tracks

        if "entries" in data:
            # Playlist or search results
            entries = data["entries"]
            for e in entries:
                if not e:
                    continue
                if "url" not in e:
                    # sometimes yt-dlp returns flat entries; re-extract
                    def re_extract():
                        with yt_dlp.YoutubeDL(YTDL_OPTS) as y:
                            return y.extract_info(e.get("url") or e.get("webpage_url"), download=False)
                    e = await loop.run_in_executor(None, re_extract)

                stream_url = e.get("url")
                webpage_url = e.get("webpage_url") or e.get("original_url") or stream_url
                title = e.get("title") or "Unknown Title"
                duration = e.get("duration")
                thumb = (e.get("thumbnail")
                         or (e.get("thumbnails")[0]["url"] if e.get("thumbnails") else None))
                if stream_url:
                    tracks.append(Track(title, stream_url, webpage_url, duration, requester, thumb))
        else:
            # Single video
            e = data
            stream_url = e.get("url")
            webpage_url = e.get("webpage_url") or e.get("original_url") or stream_url
            title = e.get("title") or "Unknown Title"
            duration = e.get("duration")
            thumb = (e.get("thumbnail")
                     or (e.get("thumbnails")[0]["url"] if e.get("thumbnails") else None))
            if stream_url:
                tracks.append(Track(title, stream_url, webpage_url, duration, requester, thumb))

        return tracks

    async def _connect_where_user_is(self, ctx_or_inter: commands.Context | discord.Interaction):
        """Connect/move bot to the invoker's voice channel."""
        if isinstance(ctx_or_inter, commands.Context):
            user = ctx_or_inter.author
            guild = ctx_or_inter.guild
            text = ctx_or_inter.channel
        else:
            user = ctx_or_inter.user
            guild = ctx_or_inter.guild
            text = ctx_or_inter.channel

        if not user or not isinstance(user, (discord.Member,)):
            raise commands.CommandError("Couldn’t find your member info.")
        if not user.voice or not user.voice.channel:
            raise commands.CommandError("❌ You must be in a voice channel.")

        player = self.get_player(guild)
        player.text_channel = text  # set announcement channel
        await player.ensure_connected(user.voice.channel)
        return player

    # ---------- Commands ----------
    async def _cmd_play_impl(self, ctx_or_inter, query: str):
        player = await self._connect_where_user_is(ctx_or_inter)

        # detect explicit playlist URL?
        for_playlist = bool(YOUTUBE_PLAYLIST_RE.search(query)) or bool(YOUTUBE_URL_RE.search(query))

        tracks = await self._yt_search_or_url(query, requester=ctx_or_inter.user if isinstance(ctx_or_inter, discord.Interaction) else ctx_or_inter.author, for_playlist=for_playlist)

        if not tracks:
            msg = "❌ Couldn’t find anything to play."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.reply(msg)
            else:
                return await ctx_or_inter.followup.send(msg)

        # Enqueue
        player.enqueue(tracks)
        player.notify_new_tracks()

        if len(tracks) == 1:
            msg = f"➕ Queued: **{tracks[0].title}**"
        else:
            msg = f"➕ Queued **{len(tracks)}** tracks{' (playlist)' if for_playlist else ''}."

        if isinstance(ctx_or_inter, commands.Context):
            await ctx_or_inter.reply(msg)
        else:
            await ctx_or_inter.followup.send(msg)

    # PLAY
    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        await self._maybe_defer_prefix(ctx)
        await self._cmd_play_impl(ctx, query)

    @app_commands.command(name="play", description="Play a song or a YouTube playlist / search")
    @app_commands.describe(query="Search terms or a YouTube URL/playlist URL")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await self._cmd_play_impl(interaction, query)

    # PAUSE
    @commands.command(name="pause")
    async def pause_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.reply("⏸️ Paused.")

    @app_commands.command(name="pause", description="Pause the music")
    async def pause_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    # RESUME
    @commands.command(name="resume")
    async def resume_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.reply("▶️ Resumed.")

    @app_commands.command(name="resume", description="Resume the music")
    async def resume_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is paused.", ephemeral=True)

    # SKIP
    @commands.command(name="skip")
    async def skip_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.reply("⏭️ Skipped.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)

    # STOP
    @commands.command(name="stop")
    async def stop_prefix(self, ctx: commands.Context):
        await self._stop_common(ctx.guild)
        await ctx.reply("🛑 Stopped and disconnected.")

    @app_commands.command(name="stop", description="Stop and disconnect")
    async def stop_slash(self, interaction: discord.Interaction):
        await self._stop_common(interaction.guild)
        await interaction.response.send_message("🛑 Stopped and disconnected.", ephemeral=True)

    async def _stop_common(self, guild: discord.Guild):
        player = self.get_player(guild)
        player.queue.clear()
        player.current = None
        vc = guild.voice_client
        if vc:
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass
        await player._disconnect_cleanup()

    # QUEUE
    @commands.command(name="queue", aliases=["q"])
    async def queue_prefix(self, ctx: commands.Context):
        await self._send_queue(ctx.channel, ctx.guild)

    @app_commands.command(name="queue", description="Show the queue")
    async def queue_slash(self, interaction: discord.Interaction):
        await self._send_queue(interaction.channel, interaction.guild)
        await interaction.response.send_message("📜 Sent the queue.", ephemeral=True)

    async def _send_queue(self, channel: discord.abc.Messageable, guild: discord.Guild):
        player = self.get_player(guild)
        desc = ""
        if player.current:
            desc += f"**Now:** {player.current.title}\n\n"
        if player.queue:
            for i, t in enumerate(list(player.queue)[:15], start=1):
                desc += f"`{i}.` {t.title}\n"
            if len(player.queue) > 15:
                desc += f"... and {len(player.queue) - 15} more"
        else:
            desc += "_Queue is empty._"
        embed = discord.Embed(title="Queue", description=desc, color=discord.Color.blurple())
        await channel.send(embed=embed)

    # NOW PLAYING
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx: commands.Context):
        await self._nowplaying_common(ctx)

    @app_commands.command(name="nowplaying", description="Show the currently playing track")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=False)
        await self._nowplaying_common(interaction, ephemeral=True)

    async def _nowplaying_common(self, ctx_or_inter, ephemeral: bool = False):
        guild = ctx_or_inter.guild
        player = self.get_player(guild)
        if not player.current:
            msg = "🛑 Music stopped, nothing playing."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.reply(msg)
            return await ctx_or_inter.followup.send(msg, ephemeral=ephemeral)

        t = player.current
        embed = discord.Embed(title="Now Playing", description=f"**{t.title}**", color=discord.Color.green())
        if t.thumbnail:
            embed.set_thumbnail(url=t.thumbnail)
        embed.add_field(name="Requested by", value=t.requester.mention, inline=True)
        if t.webpage_url:
            embed.add_field(name="Link", value=t.webpage_url, inline=True)
            if isinstance(ctx_or_inter, commands.Context):
                await ctx_or_inter.send(embed=embed)
            else:
                await ctx_or_inter.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
