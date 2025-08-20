import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from typing import Optional, List, Dict
from collections import defaultdict


# ======================
# YTDL + FFMPEG CONFIG
# ======================
ytdl_format_options = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": False,   # allow playlists
    "quiet": True,
    "default_search": "auto",
    "extract_flat": False,
    "source_address": "0.0.0.0",
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class Track:
    __slots__ = ("title", "webpage_url", "duration", "thumbnail", "requester")

    def __init__(self, *, title: str, webpage_url: str, duration: Optional[int], thumbnail: Optional[str], requester):
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


async def fetch_tracks(query: str, requester) -> List[Track]:
    def do_extract():
        return ytdl.extract_info(query, download=False)

    data = await asyncio.get_running_loop().run_in_executor(None, do_extract)
    if not data:
        raise RuntimeError("No data from extractor.")

    entries = []
    if "entries" in data:
        entries = [e for e in data["entries"] if e]
    else:
        entries = [data]

    tracks = []
    for d in entries:
        tracks.append(
            Track(
                title=d.get("title", "Unknown Title"),
                webpage_url=d.get("webpage_url") or d.get("original_url") or query,
                duration=d.get("duration"),
                thumbnail=d.get("thumbnail"),
                requester=requester,
            )
        )
    return tracks


async def get_stream_url(webpage_url: str) -> str:
    def do_extract():
        data = ytdl.extract_info(webpage_url, download=False)
        if "entries" in data:
            data = data["entries"][0]
        return data["url"]

    return await asyncio.get_running_loop().run_in_executor(None, do_extract)


# ======================
# MUSIC COG
# ======================
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues: Dict[int, List[Track]] = defaultdict(list)
        self.currents: Dict[int, Optional[Track]] = {}
        self.loop_flags: Dict[int, bool] = defaultdict(bool)
        self.idle_timeout = 300
        self.idle_tasks: Dict[int, asyncio.Task] = {}

    # --------- helpers ---------
    def get_queue(self, guild_id: int) -> List[Track]:
        return self.queues[guild_id]

    async def ensure_voice(self, channel: discord.VoiceChannel, guild: discord.Guild) -> discord.VoiceClient:
        vc = guild.voice_client
        if vc and vc.channel != channel:
            await vc.move_to(channel)
        elif not vc:
            vc = await channel.connect()
        return vc

    async def start_playback(self, guild: discord.Guild, text_channel: discord.abc.Messageable):
        queue = self.get_queue(guild.id)
        if not queue:
            return
        vc = guild.voice_client
        if not vc or vc.is_playing() or vc.is_paused():
            return

        track = queue.pop(0)
        self.currents[guild.id] = track
        stream_url = await get_stream_url(track.webpage_url)

        def after_play(err):
            fut = self.bot.loop.create_task(self._after_track(guild, text_channel, had_error=err))
            fut.add_done_callback(lambda f: f.exception())

        opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }
        vc.play(discord.FFmpegPCMAudio(stream_url, **opts), after=after_play)
        await self.announce_now_playing(text_channel, track)

    async def _after_track(self, guild: discord.Guild, text_channel: discord.abc.Messageable, had_error):
        if had_error:
            await text_channel.send(f"⚠️ Playback error: {had_error}")

        played = self.currents.get(guild.id)
        self.currents[guild.id] = None
        if played and self.loop_flags[guild.id]:
            self.queues[guild.id].append(played)

        if not self.get_queue(guild.id):
            await self.start_idle_timer(guild, text_channel)
        await self.start_playback(guild, text_channel)

    async def start_idle_timer(self, guild: discord.Guild, channel: discord.abc.Messageable):
        if guild.id in self.idle_tasks:
            self.idle_tasks[guild.id].cancel()

        async def waiter():
            try:
                await asyncio.sleep(self.idle_timeout)
                vc = guild.voice_client
                if vc and (not vc.is_playing() and not self.get_queue(guild.id)):
                    await channel.send("🕒 Idle for 5 minutes — disconnecting.")
                    await self.disconnect_cleanup(vc, guild.id)
            except asyncio.CancelledError:
                pass

        self.idle_tasks[guild.id] = self.bot.loop.create_task(waiter())

    async def disconnect_cleanup(self, vc: discord.VoiceClient, guild_id: int):
        if vc.is_playing():
            vc.stop()
        await vc.disconnect()
        self.queues[guild_id].clear()
        self.currents[guild_id] = None
        if guild_id in self.idle_tasks:
            self.idle_tasks[guild_id].cancel()
            del self.idle_tasks[guild_id]

    async def enqueue(self, query: str, requester, text_channel: discord.abc.Messageable, guild: discord.Guild):
        tracks = await fetch_tracks(query, requester)
        q = self.get_queue(guild.id)
        q.extend(tracks)
        if len(tracks) == 1:
            await self.announce_enqueued(text_channel, tracks[0], len(q))
        else:
            await text_channel.send(f"✅ Added **{len(tracks)} tracks** to the queue.")
        return tracks

    # --------- announce ---------
    async def announce_enqueued(self, channel, track: Track, pos: int):
        embed = discord.Embed(
            title=track.title,
            url=track.webpage_url,
            description=f"Added by {getattr(track.requester, 'mention', str(track.requester))}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Length", value=track.pretty_duration(), inline=True)
        embed.add_field(name="Position in queue", value=str(pos), inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await channel.send(embed=embed)

    async def announce_now_playing(self, channel, track: Track):
        embed = discord.Embed(
            title=f"Now Playing — {track.title}",
            url=track.webpage_url,
            color=discord.Color.green(),
        )
        embed.add_field(name="Length", value=track.pretty_duration(), inline=True)
        embed.add_field(name="Requested by", value=getattr(track.requester, 'mention', str(track.requester)), inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await channel.send(embed=embed)

    # --------- commands ---------
    async def _handle_play(self, voice_channel, guild, text_channel, query, requester):
        await self.ensure_voice(voice_channel, guild)
        await self.enqueue(query, requester, text_channel, guild)
        await self.start_playback(guild, text_channel)

    # PLAY
    @commands.command(name="play")
    async def play_cmd(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You are not in a voice channel.")
        await self._handle_play(ctx.author.voice.channel, ctx.guild, ctx.channel, query, ctx.author)

    @app_commands.command(name="play", description="Play a song or playlist")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You are not in a voice channel.", ephemeral=True)
        await interaction.response.defer(thinking=True)
        await self._handle_play(interaction.user.voice.channel, interaction.guild, interaction.channel, query, interaction.user)
        await interaction.followup.send("✅ Added to queue.")

    # QUEUE
    @commands.command(name="queue")
    async def queue_show(self, ctx: commands.Context):
        await self._queue_display(ctx.channel, ctx.guild)

    @app_commands.command(name="queue", description="Show the current queue")
    async def slash_queue(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._queue_display(interaction.channel, interaction.guild)

    async def _queue_display(self, channel, guild):
        q = self.get_queue(guild.id)
        if not q:
            return await channel.send("(Queue is empty)")
        lines = [f"**{i+1}.** [{t.title}]({t.webpage_url}) • {t.pretty_duration()} • {getattr(t.requester, 'mention', str(t.requester))}" for i, t in enumerate(q)]
        embed = discord.Embed(title="Queue", description="\n".join(lines)[:4000], color=discord.Color.blurple())
        await channel.send(embed=embed)

    # SKIP
    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        await self._skip(ctx.guild, ctx.channel)

    @app_commands.command(name="skip", description="Skip the current song")
    async def slash_skip(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._skip(interaction.guild, interaction.channel)

    async def _skip(self, guild, channel):
        vc = guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await channel.send("⏭️ Skipped.")
        else:
            await channel.send("❌ Nothing is playing.")

    # STOP
    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        await self._stop(ctx.guild, ctx.channel)

    @app_commands.command(name="stop", description="Stop music and leave")
    async def slash_stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._stop(interaction.guild, interaction.channel)

    async def _stop(self, guild, channel):
        vc = guild.voice_client
        if vc:
            await self.disconnect_cleanup(vc, guild.id)
            await channel.send("🛑 Stopped and left.")
        else:
            await channel.send("❌ Not connected.")

    # LOOP
    @commands.command(name="loop")
    async def loop_(self, ctx: commands.Context):
        await self._loop(ctx.guild, ctx.channel)

    @app_commands.command(name="loop", description="Toggle looping the current song")
    async def slash_loop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._loop(interaction.guild, interaction.channel)

    async def _loop(self, guild, channel):
        self.loop_flags[guild.id] = not self.loop_flags[guild.id]
        await channel.send(f"🔁 Loop is now {'enabled' if self.loop_flags[guild.id] else 'disabled'}.")

    # NOW PLAYING
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        await self._np(ctx.guild, ctx.channel)

    @app_commands.command(name="nowplaying", description="Show the current song")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._np(interaction.guild, interaction.channel)

    async def _np(self, guild, channel):
        track = self.currents.get(guild.id)
        vc = guild.voice_client
        if vc and track and (vc.is_playing() or vc.is_paused()):
            await self.announce_now_playing(channel, track)
        else:
            await channel.send("❌ Nothing is playing.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
