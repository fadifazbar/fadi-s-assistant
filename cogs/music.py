import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import random
import asyncio
from typing import Optional, List

# ======================
# YTDL + FFMPEG CONFIG
# ======================
ytdl_format_options = {
    "format": "bestaudio[ext=webm]/bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "default_search": "auto",
    "extract_flat": False,
    "geo_bypass": True,
    "source_address": "0.0.0.0",
    "ignoreerrors": True,
    "http_headers": {"User-Agent": "Mozilla/5.0"},
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
ffmpeg_options = {"options": "-vn"}

# ======================
# TRACK / SOURCE
# ======================
class Track:
    __slots__ = ("title", "url", "webpage_url", "duration", "thumbnail", "requester", "query")

    def __init__(self, *, title: str, url: str, webpage_url: str, duration: Optional[int], thumbnail: Optional[str], requester, query: str):
        self.title = title
        self.url = url
        self.webpage_url = webpage_url
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
        self.query = query

    def pretty_duration(self) -> str:
        if self.duration is None:
            return "?"
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, track: Track):
        super().__init__(source)
        self.track = track

    @classmethod
    async def create_source(cls, track: Track):
        opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }
        return cls(discord.FFmpegPCMAudio(track.url, **opts), track=track)

# ======================
# FETCH TRACK
# ======================
async def fetch_track(query: str, requester) -> Track:
    loop = asyncio.get_running_loop()
    def do_extract():
        data = ytdl.extract_info(query, download=False)
        if not data:
            raise RuntimeError("Could not extract info.")
        if "entries" in data:
            data = data["entries"][0] if isinstance(data["entries"], list) else data["entries"]
        return data
    data = await loop.run_in_executor(None, do_extract)
    return Track(
        title=data.get("title", "Unknown Title"),
        url=data.get("url"),
        webpage_url=data.get("webpage_url") or data.get("original_url") or query,
        duration=data.get("duration"),
        thumbnail=data.get("thumbnail"),
        requester=requester,
        query=query
    )

# ======================
# MUSIC COG
# ======================
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.previous: Optional[Track] = None
        self.loop_queue = False
        self.idle_timeout = 300
        self.idle_task: Optional[asyncio.Task] = None

    # ----------- VOICE HELPERS -----------
    async def ensure_voice(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        vc = channel.guild.voice_client
        if vc and vc.channel != channel:
            await vc.move_to(channel)
        elif not vc:
            vc = await channel.connect()
        return vc

    async def start_playback_if_idle(self, guild: discord.Guild, text_channel: discord.abc.Messageable):
        vc = guild.voice_client
        if not vc or vc.is_playing() or vc.is_paused() or not self.queue:
            return

        next_track = self.queue.pop(0)
        if self.current:
            self.previous = self.current
        self.current = next_track

        source = await YTDLSource.create_source(next_track)

        def after_play(err):
            fut = self.bot.loop.create_task(self._after_track(guild, text_channel, err))
            try: fut.add_done_callback(lambda f: f.exception())
            except Exception: pass

        vc.play(source, after=after_play)
        await self.cancel_idle_timer()
        await self.announce_now_playing(text_channel, next_track)

    async def _after_track(self, guild: discord.Guild, text_channel: discord.abc.Messageable, err):
        if err:
            await text_channel.send(f"⚠️ Playback error: {err}")
        played = self.current
        self.current = None
        if self.loop_queue and played:
            self.queue.append(played)
        if not self.queue:
            await self.start_idle_timer(text_channel)
        else:
            await self.start_playback_if_idle(guild, text_channel)

    async def start_idle_timer(self, channel: discord.abc.Messageable):
        await self.cancel_idle_timer()
        async def idle_wait():
            await asyncio.sleep(self.idle_timeout)
            vc = channel.guild.voice_client
            if vc and not vc.is_playing() and not self.queue:
                await channel.send("🕒 No music for 5 minutes — disconnecting.")
                await vc.disconnect()
                self.current = None
        self.idle_task = asyncio.create_task(idle_wait())

    async def cancel_idle_timer(self):
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
        self.idle_task = None

    # ----------- QUEUE MANAGEMENT -----------
    async def enqueue(self, query: str, requester, text_channel: discord.abc.Messageable):
        track = await fetch_track(query, requester)
        self.queue.append(track)
        await self.announce_enqueued(text_channel, track)
        return track

    async def do_back(self, ctx_or_inter):
        is_interaction = isinstance(ctx_or_inter, discord.Interaction)
        guild = ctx_or_inter.guild
        vc = guild.voice_client
        if not self.previous or not vc:
            msg = "⚠️ No previous track!"
            return (await ctx_or_inter.send(msg) if not is_interaction else await ctx_or_inter.response.send_message(msg, ephemeral=True))

        if self.current:
            self.queue.insert(0, self.current)
        self.current, self.previous = self.previous, self.current
        source = await YTDLSource.create_source(self.current)
        vc.stop()
        vc.play(source, after=lambda _: self.bot.loop.create_task(self.start_playback_if_idle(guild, self._pick_announce_channel(guild))))
        embed = discord.Embed(title="⏮️ Back", description=f"Now playing: [{self.current.title}]({self.current.webpage_url})", color=discord.Color.orange())
        embed.set_thumbnail(url=self.current.thumbnail)
        return (await ctx_or_inter.send(embed=embed) if not is_interaction else await ctx_or_inter.response.send_message(embed=embed))

    # ----------- ANNOUNCEMENTS -----------
    async def announce_enqueued(self, channel, track):
        embed = discord.Embed(title=track.title, url=track.webpage_url,
                              description=f"Added to queue by {getattr(track.requester, 'mention', str(track.requester))}",
                              color=discord.Color.blurple())
        embed.add_field(name="Length", value=track.pretty_duration())
        embed.add_field(name="Position in queue", value=str(len(self.queue)))
        if track.thumbnail: embed.set_thumbnail(url=track.thumbnail)
        await channel.send(embed=embed)

    async def announce_now_playing(self, channel, track):
        embed = discord.Embed(title=f"Now Playing — {track.title}", url=track.webpage_url, color=discord.Color.green())
        embed.add_field(name="Length", value=track.pretty_duration())
        embed.add_field(name="Requested by", value=getattr(track.requester, "mention", str(track.requester)))
        if track.thumbnail: embed.set_thumbnail(url=track.thumbnail)
        await channel.send(embed=embed)

    def _pick_announce_channel(self, guild: discord.Guild):
        ch = getattr(guild, "system_channel", None)
        if ch and ch.permissions_for(guild.me).send_messages: return ch
        for c in guild.text_channels:
            if c.permissions_for(guild.me).send_messages: return c
        return None

    # ----------- COMMANDS -----------
    @commands.command(name="play")
    async def play_cmd(self, ctx, *, query: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ Not in VC")
        await self.enqueue(query, ctx.author, ctx.channel)
        await self.start_playback_if_idle(ctx.guild, ctx.channel)

    @commands.command(name="skip")
    async def skip(self, ctx):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Skipped")
        else: await ctx.send("❌ Nothing playing")

    @commands.command(name="back")
    async def back(self, ctx): await self.do_back(ctx)

    @commands.command(name="stop")
    async def stop(self, ctx):
        vc = ctx.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
            self.current = None
            await ctx.send("🛑 Stopped and left VC")
        else: await ctx.send("❌ Not connected")

# ======================
# COG SETUP
# ======================
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))

