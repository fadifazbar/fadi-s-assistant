import discord
from discord.ext import commands
import asyncio
import yt_dlp
from typing import Optional, List, Dict
from collections import defaultdict

# ---------- YTDL Options ----------
ytdl_format_options = {
    "format": "bestaudio[ext=webm]/bestaudio/best",  # avoid SABR formats
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "extract_flat": False,
    "skip_unavailable_fragments": True,
    "cachedir": False,
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# ---------- Track Wrapper ----------
class Track:
    __slots__ = ("title", "webpage_url", "duration", "thumbnail", "requester")

    def __init__(self, *, title: str, webpage_url: str, duration: Optional[int],
                 thumbnail: Optional[str], requester):
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

async def get_stream_url(webpage_url: str) -> str:
    """Re-extract fresh audio stream before playback."""
    def do_extract():
        info = ytdl.extract_info(webpage_url, download=False)
        if "entries" in info:
            info = info["entries"][0]
        return info.get("url")

    return await asyncio.get_running_loop().run_in_executor(None, do_extract)

async def fetch_tracks(query: str, requester) -> List[Track]:
    """Search YouTube and return Track objects (playlist or single)."""
    def do_extract():
        return ytdl.extract_info(query, download=False)

    data = await asyncio.get_running_loop().run_in_executor(None, do_extract)

    if data is None:
        return []

    entries = []
    if "entries" in data:  # Playlist or search results
        entries = data["entries"]
    else:
        entries = [data]

    tracks = []
    for d in entries:
        if not d or not d.get("url") or d.get("title") in (None, "[Deleted video]", "[Private video]"):
            continue  # skip broken/deleted
        tracks.append(
            Track(
                title=d.get("title", "Unknown"),
                webpage_url=d.get("webpage_url") or d.get("url"),
                duration=d.get("duration"),
                thumbnail=d.get("thumbnail"),
                requester=requester,
            )
        )
    return tracks

# ---------- Music Cog ----------
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues: Dict[int, List[Track]] = defaultdict(list)
        self.currents: Dict[int, Optional[Track]] = defaultdict(lambda: None)

    def get_queue(self, guild_id: int) -> List[Track]:
        return self.queues[guild_id]

    # ----- Core -----
    async def start_playback(self, guild: discord.Guild, text_channel: discord.abc.Messageable):
        queue = self.get_queue(guild.id)
        if not queue:
            return
        vc = guild.voice_client
        if not vc or vc.is_playing() or vc.is_paused():
            return

        track = queue.pop(0)
        self.currents[guild.id] = track

        # fresh stream url
        stream_url = await get_stream_url(track.webpage_url)
        if not stream_url:
            await text_channel.send(f"⚠️ Could not play: {track.title}")
            return await self.start_playback(guild, text_channel)

        ffmpeg_opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }
        vc.play(
            discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts),
            after=lambda e: self.bot.loop.create_task(self._after_track(guild, text_channel, e))
        )

        await self.announce_now_playing(text_channel, track)

    async def _after_track(self, guild, text_channel, error):
        if error:
            await text_channel.send(f"⚠️ Error: {error}")
        self.currents[guild.id] = None
        await self.start_playback(guild, text_channel)

    # ----- Announcements -----
    async def announce_now_playing(self, channel, track: Track):
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.green(),
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        if track.duration:
            embed.add_field(name="Duration", value=track.pretty_duration())
        embed.add_field(name="Requested by", value=str(track.requester))
        await channel.send(embed=embed)

    async def announce_enqueued(self, channel, track: Track):
        embed = discord.Embed(
            title="➕ Added to Queue",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.blurple(),
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        if track.duration:
            embed.add_field(name="Duration", value=track.pretty_duration())
        embed.add_field(name="Requested by", value=str(track.requester))
        await channel.send(embed=embed)

    # ----- Commands -----
    async def enqueue_and_play(self, ctx_or_inter, query: str, requester):
        if isinstance(ctx_or_inter, commands.Context):
            guild, channel = ctx_or_inter.guild, ctx_or_inter.channel
        else:
            guild, channel = ctx_or_inter.guild, ctx_or_inter.channel

        if not guild.voice_client:
            if requester.voice and requester.voice.channel:
                await requester.voice.channel.connect()
            else:
                return await channel.send("⚠️ You must be in a voice channel.")

        tracks = await fetch_tracks(query, requester)
        if not tracks:
            return await channel.send("❌ No valid tracks found.")

        for t in tracks:
            self.queues[guild.id].append(t)
            await self.announce_enqueued(channel, t)

        await self.start_playback(guild, channel)

    # --- Play ---
    @commands.command(name="play")
    async def play_prefix(self, ctx, *, query: str):
        await self.enqueue_and_play(ctx, query, ctx.author)

    @commands.hybrid_command(name="play")
    async def play_slash(self, ctx, *, query: str):
        await self.enqueue_and_play(ctx, query, ctx.author)

    # --- Skip ---
    @commands.command(name="skip")
    async def skip_prefix(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Skipped.")

    @commands.hybrid_command(name="skip")
    async def skip_slash(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Skipped.")

    # --- Queue ---
    @commands.command(name="queue")
    async def queue_prefix(self, ctx):
        q = self.get_queue(ctx.guild.id)
        if not q:
            return await ctx.send("🎵 Queue is empty.")
        desc = "\n".join(f"{i+1}. {t.title} ({t.pretty_duration()})" for i, t in enumerate(q[:10]))
        await ctx.send(embed=discord.Embed(title="Queue", description=desc))

    @commands.hybrid_command(name="queue")
    async def queue_slash(self, ctx):
        await self.queue_prefix(ctx)

    # --- Leave ---
    @commands.command(name="leave")
    async def leave_prefix(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Left the channel.")

    @commands.hybrid_command(name="leave")
    async def leave_slash(self, ctx):
        await self.leave_prefix(ctx)

# ---------- Setup ----------
async def setup(bot):
    await bot.add_cog(Music(bot))
