import asyncio
from typing import Optional, List, Dict
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp


# ======================
# yt-dlp & ffmpeg config
# ======================
YTDL_OPTS = {
    # Prefer direct audio streams (m4a/webm). This helps avoid SABR/HLS weirdness.
    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    "noplaylist": False,                 # ✅ allow playlists
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "retries": 3,
    "skip_unavailable_fragments": True,
    "ignoreerrors": "only_download",     # skip broken entries in playlists
    # Try a client profile less likely to hit SABR-only formats
    "extractor_args": {"youtube": {"player_client": ["android"]}},
    "cachedir": False,
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

FFMPEG_OPTS = {
    # Reconnect flags: keeps long songs from dying on transient resets
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


# =========
# Track DTO
# =========
class Track:
    __slots__ = ("title", "webpage_url", "duration", "thumbnail", "requester")

    def __init__(
        self,
        *,
        title: str,
        webpage_url: str,
        duration: Optional[int],
        thumbnail: Optional[str],
        requester,
    ):
        self.title = title
        self.webpage_url = webpage_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester

    def pretty_duration(self) -> str:
        if self.duration is None:
            return "?"
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ======================
# yt-dlp helper routines
# ======================
async def _extract(query: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))


async def _fresh_stream_url(webpage_url: str) -> Optional[str]:
    """Re-extract the stream URL right before playback to avoid expiry/cutoffs."""
    info = await _extract(webpage_url)
    if not info:
        return None
    if "entries" in info:
        info = info["entries"][0]
    return info.get("url")


def _is_unplayable(entry: dict) -> bool:
    if not entry:
        return True
    title = entry.get("title")
    if title in (None, "[Deleted video]", "[Private video]"):
        return True
    if entry.get("availability") in ("private", "needs_auth"):
        return True
    # Some playlist entries come as "url": <id> (not full URL). We'll fix that later.
    return False


def _entry_to_track(entry: dict, requester) -> Optional[Track]:
    if _is_unplayable(entry):
        return None

    # Build a usable watch URL if needed
    webpage_url = entry.get("webpage_url")
    if not webpage_url:
        vid_id = entry.get("id")
        if vid_id:
            webpage_url = f"https://www.youtube.com/watch?v={vid_id}"
        else:
            # fall back to direct url; if neither is present, skip
            webpage_url = entry.get("url")
    if not webpage_url:
        return None

    return Track(
        title=entry.get("title", "Unknown Title"),
        webpage_url=webpage_url,
        duration=entry.get("duration"),
        thumbnail=entry.get("thumbnail"),
        requester=requester,
    )


# ==========
# Music Cog
# ==========
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues: Dict[int, List[Track]] = {}
        self.currents: Dict[int, Optional[Track]] = {}

    # auto-sync slash commands when cog loads (so /play shows up)
    async def cog_load(self):
        try:
            await self.bot.tree.sync()
        except Exception:
            pass

    # ---------- queue helpers ----------
    def _queue(self, guild_id: int) -> List[Track]:
        return self.queues.setdefault(guild_id, [])

    async def _ensure_voice(self, guild: discord.Guild, voice_channel: discord.VoiceChannel):
        vc = guild.voice_client
        if vc and vc.channel != voice_channel:
            await vc.move_to(voice_channel)
        elif not vc:
            await voice_channel.connect()

    async def _announce_now(self, channel: discord.abc.Messageable, track: Track):
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.green(),
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        if track.duration:
            embed.add_field(name="Duration", value=track.pretty_duration(), inline=True)
        embed.add_field(
            name="Requested by",
            value=getattr(track.requester, "mention", str(track.requester)),
            inline=True,
        )
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

    async def _start_if_idle(self, guild: discord.Guild, channel: discord.abc.Messageable):
        vc = guild.voice_client
        q = self._queue(guild.id)
        if not vc or vc.is_playing() or vc.is_paused() or not q:
            return

        track = q.pop(0)
        self.currents[guild.id] = track

        stream_url = await _fresh_stream_url(track.webpage_url)
        if not stream_url:
            await channel.send(f"⚠️ Could not fetch stream for **{track.title}** — skipping.")
            self.currents[guild.id] = None
            return await self._start_if_idle(guild, channel)

        def _after(err: Optional[Exception]):
            fut = self.bot.loop.create_task(self._after_track(guild, channel, err))
            fut.add_done_callback(lambda f: f.exception())

        vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTS), after=_after)
        await self._announce_now(channel, track)

    async def _after_track(self, guild: discord.Guild, channel: discord.abc.Messageable, err):
        if err:
            await channel.send(f"⚠️ Playback error: {err}")
        self.currents[guild.id] = None
        await self._start_if_idle(guild, channel)

    # ---------- core action ----------
    async def _handle_play(self, guild: discord.Guild, text_channel: discord.abc.Messageable, requester, query: str):
        # fetch info in background (fast command response)
        try:
            info = await _extract(query)
        except Exception as e:
            await text_channel.send(f"❌ Error: `{e}`")
            return

        tracks_to_add: List[Track] = []
        if not info:
            await text_channel.send("❌ No results.")
            return

        if "entries" in info:  # playlist or search results
            for entry in info["entries"] or []:
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

        # Feedback
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

    @commands.command(name="queue", help="Show the current queue.")
    async def queue_prefix(self, ctx: commands.Context):
        q = self._queue(ctx.guild.id)
        if not q:
            return await ctx.send("(Queue is empty)")
        lines = [
            f"**{i+1}.** [{t.title}]({t.webpage_url}) — {t.pretty_duration()} • {getattr(t.requester, 'mention', t.requester)}"
            for i, t in enumerate(q)
        ]
        embed = discord.Embed(title="Queue", description="\n".join(lines)[:4000], color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @commands.command(name="skip", help="Skip the current song.")
    async def skip_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="nowplaying", aliases=["np"], help="Show the current track.")
    async def nowplaying_prefix(self, ctx: commands.Context):
        track = self.currents.get(ctx.guild.id)
        vc = ctx.guild.voice_client
        if vc and track and (vc.is_playing() or vc.is_paused()):
            await self._announce_now(ctx.channel, track)
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="stopmusic", help="Stop music and leave the voice channel.")
    async def stopmusic_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc:
            if vc.is_playing():
                vc.stop()
            await vc.disconnect()
            self.queues[ctx.guild.id] = []
            self.currents[ctx.guild.id] = None
            await ctx.send("🛑 Stopped music and left the channel.")
        else:
            await ctx.send("❌ Not connected.")

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
            await interaction.followup.send("✅ Queued.")
        except discord.HTTPException:
            pass

    @app_commands.command(name="queue", description="Show the current queue.")
    async def queue_slash(self, interaction: discord.Interaction):
        q = self._queue(interaction.guild.id)
        if not q:
            return await interaction.response.send_message("(Queue is empty)", ephemeral=True)
        lines = [
            f"**{i+1}.** [{t.title}]({t.webpage_url}) — {t.pretty_duration()} • {getattr(t.requester, 'mention', t.requester)}"
            for i, t in enumerate(q)
        ]
        embed = discord.Embed(title="Queue", description="\n".join(lines)[:4000], color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="nowplaying", description="Show the current track.")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        track = self.currents.get(interaction.guild.id)
        vc = interaction.guild.voice_client
        if vc and track and (vc.is_playing() or vc.is_paused()):
            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"[{track.title}]({track.webpage_url})",
                color=discord.Color.green(),
            )
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            if track.duration:
                embed.add_field(name="Duration", value=track.pretty_duration(), inline=True)
            embed.add_field(name="Requested by", value=getattr(track.requester, "mention", str(track.requester)), inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @app_commands.command(name="stopmusic", description="Stop music and leave the voice channel.")
    async def stopmusic_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing():
                vc.stop()
            await vc.disconnect()
            self.queues[interaction.guild.id] = []
            self.currents[interaction.guild.id] = None
            await interaction.response.send_message("🛑 Stopped music and left the channel.")
        else:
            await interaction.response.send_message("❌ Not connected.", ephemeral=True)


# ===========
# Cog loader
# ===========
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
