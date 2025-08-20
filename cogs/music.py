import asyncio
import re
import random
from typing import Optional, List, Dict, Literal

import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp

# ======================
# yt-dlp & ffmpeg config
# ======================
YTDL_BASE = {
    # Prefer direct audio streams (m4a/webm). Helps avoid SABR/HLS issues.
    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "retries": 3,
    "skip_unavailable_fragments": True,
    "ignoreerrors": "only_download",
    # Use a client profile less likely to hit SABR-only formats
    "extractor_args": {"youtube": {"player_client": ["android"]}},
    "cachedir": False,
}

# Main YDL (full extraction)
_ytdl = yt_dlp.YoutubeDL(YTDL_BASE)
# Flat extractor for fast playlist enumeration
_flat_ytdl = yt_dlp.YoutubeDL({**YTDL_BASE, "extract_flat": "in_playlist"})

# FFMPEG flags (keep long songs stable)
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# =========
# Track DTO
# =========
class Track:
    __slots__ = ("title", "webpage_url", "duration", "thumbnail", "requester", "uploader")

    def __init__(
        self,
        *,
        title: str,
        webpage_url: str,
        duration: Optional[int],
        thumbnail: Optional[str],
        requester,
        uploader: Optional[str] = None,
    ):
        self.title = title
        self.webpage_url = webpage_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
        self.uploader = uploader

    def pretty_duration(self) -> str:
        if self.duration is None:
            return "?"
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ======================
# yt-dlp helper routines
# ======================
async def _extract(query: str, *, flat: bool = False):
    # Offload to thread for snappier event loop
    ydl = _flat_ytdl if flat else _ytdl
    return await asyncio.to_thread(lambda: ydl.extract_info(query, download=False))

async def _fresh_stream_url(webpage_url: str, *, max_tries: int = 2) -> Optional[str]:
    """Re-extract the stream URL right before playback to avoid expiry/cutoffs.
    Retries once if needed.
    """
    last_error = None
    for _ in range(max_tries):
        try:
            info = await _extract(webpage_url, flat=False)
            if not info:
                return None
            if "entries" in info:
                info = info["entries"][0]
            url = info.get("url")
            if url:
                return url
            for fmt in (info.get("formats") or []):
                if fmt.get("acodec") not in (None, "none") and fmt.get("url"):
                    return fmt["url"]
        except Exception as e:
            last_error = e
            await asyncio.sleep(0.3)
    return None

# ==============
# URL detection
# ==============
_URL_RE = re.compile(r"^https?://", re.I)

def _looks_like_url(s: str) -> bool:
    return bool(_URL_RE.match(s or ""))


def _is_youtube_playlist_url(url: str) -> bool:
    if not _looks_like_url(url):
        return False
    return ("youtube.com" in url or "youtu.be" in url) and ("list=" in url)


# ==============
# Helpers
# ==============
LoopMode = Literal["off", "one", "all"]


def _progress_bar(elapsed: int, total: Optional[int], width: int = 18) -> str:
    if not total or total <= 0:
        return "▬" * width
    filled = int(width * min(elapsed / total, 1.0))
    return ("▬" * max(filled - 1, 0)) + "🔘" + ("▬" * (width - filled))


def _entry_to_track(entry: dict, requester) -> Optional[Track]:
    if not entry:
        return None
    title = entry.get("title")
    if title in (None, "[Deleted video]", "[Private video]"):
        return None
    if entry.get("availability") in ("private", "needs_auth"):
        return None
    live_status = entry.get("live_status")
    if live_status in ("is_live", "is_upcoming"):
        return None

    webpage_url = entry.get("webpage_url")
    if not webpage_url:
        vid_id = entry.get("id")
        if vid_id:
            webpage_url = f"https://www.youtube.com/watch?v={vid_id}"
        else:
            webpage_url = entry.get("url")
    if not webpage_url:
        return None

    return Track(
        title=title or "Unknown Title",
        webpage_url=webpage_url,
        duration=entry.get("duration"),
        thumbnail=entry.get("thumbnail"),
        requester=requester,
        uploader=entry.get("uploader") or entry.get("channel")
    )


# ==============
# Queue View (buttons)
# ==============
class QueueView(discord.ui.View):
    def __init__(self, cog: "Music", guild_id: int, user: discord.abc.User, per_page: int = 10):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        self.user = user
        self.per_page = per_page
        self.page = 0

    def _page_count(self, q_len: int) -> int:
        return max((q_len - 1) // self.per_page + 1, 1)

    def format_page(self) -> discord.Embed:
        q = self.cog._queue(self.guild_id)
        total = len(q)
        if not q:
            return discord.Embed(title="🎵 Queue", description="(empty)", color=discord.Color.blurple())
        start = self.page * self.per_page
        end = min(start + self.per_page, total)
        lines = []
        for i, t in enumerate(q[start:end], start=start):
            lines.append(
                f"**{i+1}.** [{t.title}]({t.webpage_url}) — {t.pretty_duration()} • {getattr(t.requester, 'mention', str(t.requester))}"
            )
        embed = discord.Embed(
            title="🎵 Queue",
            description="
".join(lines)[:4000] or "(no tracks on this page)",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Page {self.page+1}/{self._page_count(total)} • Total: {total}")
        return embed

    async def _ensure_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your queue view.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_author(interaction):
            return
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.format_page(), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_author(interaction):
            return
        q_len = len(self.cog._queue(self.guild_id))
        if (self.page + 1) * self.per_page < q_len:
            self.page += 1
        await interaction.response.edit_message(embed=self.format_page(), view=self)


# ==========
# Music Cog
# ==========
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues: Dict[int, List[Track]] = {}
        self.currents: Dict[int, Optional[Track]] = {}
        self.shuffle_enabled: Dict[int, bool] = {}
        self.loop_mode: Dict[int, LoopMode] = {}
        self.locks: Dict[int, asyncio.Lock] = {}
        self.idle_tasks: Dict[int, asyncio.Task] = {}

    # ------------- lifecycle -------------
    async def cog_load(self):
        try:
            await self.bot.tree.sync()
        except Exception:
            pass

    # ------------- state helpers -------------
    def _queue(self, guild_id: int) -> List[Track]:
        return self.queues.setdefault(guild_id, [])

    def _lock(self, guild_id: int) -> asyncio.Lock:
        return self.locks.setdefault(guild_id, asyncio.Lock())

    def _get_loop(self, guild_id: int) -> LoopMode:
        return self.loop_mode.get(guild_id, "off")

    def _set_loop(self, guild_id: int, mode: LoopMode):
        self.loop_mode[guild_id] = mode

    def _is_shuffle(self, guild_id: int) -> bool:
        return self.shuffle_enabled.get(guild_id, False)

    def _reset_state(self, guild_id: int):
        self.queues[guild_id] = []
        self.currents[guild_id] = None
        self.shuffle_enabled[guild_id] = False
        self.loop_mode[guild_id] = "off"
        lock = self.locks.pop(guild_id, None)
        if lock and lock.locked():
            # no direct unlock, just drop; future calls will recreate
            pass
        task = self.idle_tasks.pop(guild_id, None)
        if task:
            task.cancel()

    def _dequeue_next(self, guild_id: int) -> Optional[Track]:
        q = self._queue(guild_id)
        if not q:
            return None
        if self._is_shuffle(guild_id):
            idx = random.randrange(len(q))
            return q.pop(idx)
        return q.pop(0)

    async def _ensure_voice(self, guild: discord.Guild, voice_channel: discord.VoiceChannel):
        vc = guild.voice_client
        if vc and vc.channel != voice_channel:
            await vc.move_to(voice_channel)
        elif not vc:
            await voice_channel.connect()

    # ------------- idle cleanup -------------
    def _schedule_idle_disconnect(self, guild: discord.Guild, channel: discord.abc.Messageable, seconds: int = 120):
        async def _idle_task():
            try:
                await asyncio.sleep(seconds)
                vc = guild.voice_client
                if vc and not vc.is_playing() and not vc.is_paused() and not self._queue(guild.id):
                    await channel.send("👋 Idle for a while — disconnecting and resetting.")
                    await vc.disconnect()
                    self._reset_state(guild.id)
            except asyncio.CancelledError:
                pass
        # cancel old and schedule new
        old = self.idle_tasks.get(guild.id)
        if old:
            old.cancel()
        self.idle_tasks[guild.id] = self.bot.loop.create_task(_idle_task())

    # ------------- embeds -------------
    async def _announce_now(self, channel: discord.abc.Messageable, track: Track):
        dur = track.pretty_duration()
        bar = _progress_bar(0, track.duration)
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"[{track.title}]({track.webpage_url})
{bar}
`0:00 / {dur}`",
            color=discord.Color.green(),
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        if track.uploader:
            embed.add_field(name="Channel", value=track.uploader, inline=True)
        embed.add_field(name="Requested by", value=getattr(track.requester, "mention", str(track.requester)), inline=True)
        await channel.send(embed=embed)

    async def _announce_added(self, channel: discord.abc.Messageable, track: Track, pos: int):
        embed = discord.Embed(
            title="➕ Added to queue",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.blurple(),
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        if track.duration:
            embed.add_field(name="Duration", value=track.pretty_duration(), inline=True)
        embed.add_field(name="Position", value=str(pos), inline=True)
        await channel.send(embed=embed)

    # ------------- playback core -------------
    async def _start_if_idle(self, guild: discord.Guild, channel: discord.abc.Messageable):
        async with self._lock(guild.id):
            vc = guild.voice_client
            if not vc or vc.is_playing() or vc.is_paused():
                return

            next_track = self._dequeue_next(guild.id)
            if not next_track:
                self.currents[guild.id] = None
                self._schedule_idle_disconnect(guild, channel)
                return

            self.currents[guild.id] = next_track

            stream_url = await _fresh_stream_url(next_track.webpage_url)
            if not stream_url:
                await channel.send(f"⚠️ Could not fetch stream for **{next_track.title}** — skipping.")
                self.currents[guild.id] = None
                return await self._start_if_idle(guild, channel)

            def _after(err: Optional[Exception]):
                fut = self.bot.loop.create_task(self._after_track(guild, channel, next_track, err))
                fut.add_done_callback(lambda f: f.exception())

            vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTS), after=_after)
            await self._announce_now(channel, next_track)

    async def _after_track(self, guild: discord.Guild, channel: discord.abc.Messageable, played: Optional[Track], err):
        if err:
            await channel.send(f"⚠️ Playback error: {err}")
        # loop behavior
        mode = self._get_loop(guild.id)
        if played:
            if mode == "one":
                self._queue(guild.id).insert(0, played)  # play again immediately
            elif mode == "all":
                self._queue(guild.id).append(played)
        self.currents[guild.id] = None
        await self._start_if_idle(guild, channel)

    # ------------- play/queue logic -------------
    async def _handle_play(self, guild: discord.Guild, text_channel: discord.abc.Messageable, requester, query: str):
        try_single_search = not _looks_like_url(query)
        use_flat_playlist = _is_youtube_playlist_url(query)

        try:
            if try_single_search:
                info = await _extract(f"ytsearch1:{query}", flat=False)
            else:
                info = await _extract(query, flat=use_flat_playlist)
        except Exception as e:
            await text_channel.send(f"❌ Error: `{e}`")
            return

        if not info:
            await text_channel.send("❌ No results.")
            return

        tracks_to_add: List[Track] = []

        if (not try_single_search) and isinstance(info, dict) and info.get("_type") == "playlist" and "search" in (info.get("extractor_key", "")).lower():
            entries = (info.get("entries") or [])[:1]
            for entry in entries:
                t = _entry_to_track(entry, requester)
                if t:
                    tracks_to_add.append(t)
        elif "entries" in info:
            for entry in info.get("entries") or []:
                t = _entry_to_track(entry, requester)
                if t:
                    tracks_to_add.append(t)
        else:
            t = _entry_to_track(info, requester)
            if t:
                tracks_to_add.append(t)

        if not tracks_to_add:
            await text_channel.send("⚠️ No playable videos found (deleted/private/unavailable).")
            return

        q = self._queue(guild.id)
        start_len = len(q)
        q.extend(tracks_to_add)

        if len(tracks_to_add) == 1:
            await self._announce_added(text_channel, tracks_to_add[0], start_len + 1)
        else:
            title = info.get("title") or "playlist"
            await text_channel.send(f"📑 Added **{len(tracks_to_add)}** tracks from **{title}**.")

        await self._start_if_idle(guild, text_channel)

    # =========================
    # PREFIX COMMANDS (classic)
    # =========================
    @commands.command(name="play", help="Play a song or playlist (YouTube URL or search).")
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel.")
        await self._ensure_voice(ctx.guild, ctx.author.voice.channel)
        await self._handle_play(ctx.guild, ctx.channel, ctx.author, query)

    @commands.command(name="queue", help="Show the current queue (with buttons).")
    async def queue_prefix(self, ctx: commands.Context):
        view = QueueView(self, ctx.guild.id, ctx.author)
        await ctx.send(embed=view.format_page(), view=view)

    @commands.command(name="skip", help="Skip the current song.")
    async def skip_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="pause", help="Pause playback.")
    async def pause_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="resume", help="Resume playback.")
    async def resume_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.command(name="nowplaying", aliases=["np"], help="Show the current track.")
    async def nowplaying_prefix(self, ctx: commands.Context):
        track = self.currents.get(ctx.guild.id)
        vc = ctx.guild.voice_client
        if vc and track and (vc.is_playing() or vc.is_paused()):
            await self._announce_now(ctx.channel, track)
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="stopmusic", help="Stop music, disconnect, and reset state.")
    async def stopmusic_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc:
            if vc.is_playing():
                vc.stop()
            await vc.disconnect()
            self._reset_state(ctx.guild.id)
            await ctx.send("🛑 Stopped music, disconnected, and reset state.")
        else:
            await ctx.send("❌ Not connected.")

    @commands.command(name="shuffle", help="Toggle shuffle mode.")
    async def shuffle_prefix(self, ctx: commands.Context):
        state = not self._is_shuffle(ctx.guild.id)
        self.shuffle_enabled[ctx.guild.id] = state
        await ctx.send("🔀 Shuffle enabled." if state else "➡️ Shuffle disabled.")

    @commands.command(name="loop", help="Set loop mode: off | one | all")
    async def loop_prefix(self, ctx: commands.Context, mode: Optional[str] = None):
        valid = {"off", "one", "all"}
        if mode is None:
            return await ctx.send(f"Current loop: **{self._get_loop(ctx.guild.id)}** (choose: off/one/all)")
        if mode not in valid:
            return await ctx.send("❌ Invalid mode. Choose: off | one | all")
        self._set_loop(ctx.guild.id, mode)  # type: ignore
        await ctx.send(f"🔁 Loop set to **{mode}**.")

    # =====================
    # SLASH COMMANDS (/) 🎯
    # =====================
    @app_commands.command(name="play", description="Play a song or playlist (YouTube URL or search).")
    @app_commands.describe(query="YouTube URL or search terms")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        if not interaction.user or not isinstance(interaction.user, discord.Member) or not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
        await interaction.response.defer(thinking=True)
        await self._ensure_voice(interaction.guild, interaction.user.voice.channel)
        await self._handle_play(interaction.guild, interaction.channel, interaction.user, query)
        try:
            await interaction.followup.send("✅ Done.")
        except discord.HTTPException:
            pass

    @app_commands.command(name="queue", description="Show the current queue (with buttons).")
    async def queue_slash(self, interaction: discord.Interaction):
        view = QueueView(self, interaction.guild.id, interaction.user)
        await interaction.response.send_message(embed=view.format_page(), view=view)

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause playback.")
    async def pause_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback.")
    async def resume_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    @app_commands.command(name="nowplaying", description="Show the current track.")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        track = self.currents.get(interaction.guild.id)
        vc = interaction.guild.voice_client
        if vc and track and (vc.is_playing() or vc.is_paused()):
            await self._announce_now(interaction.channel, track)
            await interaction.response.send_message("📻 Posted now playing.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="stopmusic", description="Stop music, disconnect, and reset state.")
    async def stopmusic_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing():
                vc.stop()
            await vc.disconnect()
            self._reset_state(interaction.guild.id)
            await interaction.response.send_message("🛑 Stopped music, disconnected, and reset state.")
        else:
            await interaction.response.send_message("❌ Not connected.", ephemeral=True)

    @app_commands.choices(mode=[
        app_commands.Choice(name="off", value="off"),
        app_commands.Choice(name="one", value="one"),
        app_commands.Choice(name="all", value="all"),
    ])
    @app_commands.command(name="loop", description="Set loop mode: off | one | all")
    async def loop_slash(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        self._set_loop(interaction.guild.id, mode.value)  # type: ignore
        await interaction.response.send_message(f"🔁 Loop set to **{mode.value}**.")

    @app_commands.command(name="shuffle", description="Toggle shuffle mode.")
    async def shuffle_slash(self, interaction: discord.Interaction):
        state = not self._is_shuffle(interaction.guild.id)
        self.shuffle_enabled[interaction.guild.id] = state
        await interaction.response.send_message("🔀 Shuffle enabled." if state else "➡️ Shuffle disabled.")

    # ------------- listeners -------------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # If the bot itself left a channel, reset
        if member.id != getattr(self.bot.user, "id", None):
            return
        if before.channel and (after.channel is None or after.channel != before.channel):
            guild_id = before.channel.guild.id
            self._reset_state(guild_id)


# ===========
# Cog loader
# ===========
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
