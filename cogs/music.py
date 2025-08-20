import discord
from discord.ext import commands, tasks
from discord import app_commands
import yt_dlp
import random
import asyncio
from typing import Optional, List

# ======================
# YTDL + FFMPEG CONFIG
# ======================
ytdl_format_options = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": False,   # change to False if you want playlists
    "quiet": True,
    "default_search": "auto",
    "extract_flat": False,
    "source_address": "0.0.0.0",
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

ffmpeg_options = {"options": "-vn"}


class Track:
    __slots__ = ("title", "url", "webpage_url", "duration", "thumbnail", "requester", "query")

    def __init__(self, *, title: str, url: str, webpage_url: str, duration: Optional[int], thumbnail: Optional[str], requester, query: str):
        self.title = title
        self.url = url  # Direct stream URL
        self.webpage_url = webpage_url  # YouTube watch URL (or source page)
        self.duration = duration  # seconds
        self.thumbnail = thumbnail
        self.requester = requester
        self.query = query

    def pretty_duration(self) -> str:
        if self.duration is None:
            return "?"
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, track: Track):
        super().__init__(source)
        self.track = track

    @classmethod
    async def create_source(cls, track: Track):
        # Always re-extract the stream URL before playing (avoids cut-off on long videos)
        loop = asyncio.get_running_loop()

        def do_extract():
            return ytdl.extract_info(track.webpage_url, download=False)

        data = await loop.run_in_executor(None, do_extract)
        if "entries" in data:
            data = data["entries"][0]

        stream_url = data["url"]

        # Add reconnect options so ffmpeg continues if YouTube resets connection
        opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

        return cls(discord.FFmpegPCMAudio(stream_url, **opts), track=track)


async def fetch_track(query: str, requester) -> Track:
    def do_extract():
        data = ytdl.extract_info(query, download=False)
        if data is None:
            raise RuntimeError("Could not extract info.")
        if "entries" in data:
            data = data[0] if isinstance(data, list) else data["entries"][0]
        return data

    data = await asyncio.get_running_loop().run_in_executor(None, do_extract)
    title = data.get("title", "Unknown Title")
    url = data.get("url")  # direct stream URL
    webpage_url = data.get("webpage_url") or data.get("original_url") or query
    duration = data.get("duration")
    thumb = data.get("thumbnail")

    if not url:
        raise RuntimeError("No audio URL returned by extractor.")

    return Track(title=title, url=url, webpage_url=webpage_url, duration=duration, thumbnail=thumb, requester=requester, query=query)


# ======================
# MUSIC COG (Queue-first)
# ======================
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.loop_queue: bool = False  # Loop the entire queue as a playlist
        self.voice_cleanup_task: Optional[asyncio.Task] = None  # idle when nothing playing
        self.empty_vc_task: Optional[asyncio.Task] = None  # disconnect when VC empty
        self.idle_timeout = 300  # 5 minutes

    # --------------- helpers ---------------
    async def ensure_voice_for_context(self, channel: discord.VoiceChannel, guild: discord.Guild) -> discord.VoiceClient:
        vc = guild.voice_client
        if vc and vc.channel != channel:
            await vc.move_to(channel)
        elif not vc:
            vc = await channel.connect()
        return vc

    async def start_playback_if_idle(self, guild: discord.Guild, text_channel: discord.abc.Messageable):
        vc = guild.voice_client
        if not vc or vc.is_playing() or vc.is_paused():
            return
        if not self.queue:
            return
        # Pop next track and play
        next_track = self.queue.pop(0)
        self.current = next_track
        source = await YTDLSource.create_source(next_track)

        def after_play(err):
            # Schedule the next track on the bot loop
            fut = self.bot.loop.create_task(self._after_track(guild, text_channel, had_error=err))
            # Avoid "Task exception was never retrieved"
            try:
                fut.add_done_callback(lambda f: f.exception())
            except Exception:
                pass

        vc.play(source, after=after_play)

        # Cancel idle timers because music is playing now
        await self.cancel_idle_timers()

        # Announce now playing
        await self.announce_now_playing(text_channel, next_track)

    async def _after_track(self, guild: discord.Guild, text_channel: discord.abc.Messageable, had_error):
        if had_error:
            await text_channel.send(f"⚠️ Playback error: {had_error}")
        played = self.current
        self.current = None

        # If looping the playlist, append the track back to the end
        if self.loop_queue and played:
            self.queue.append(played)

        vc = guild.voice_client
        if vc and not self.queue:
            # nothing left -> start idle disconnect timer
            await self.start_idle_timer(text_channel, reason="no-music")
        await self.start_playback_if_idle(guild, text_channel)

    async def start_idle_timer(self, text_channel: discord.abc.Messageable, reason: str):
        await self.cancel_idle_timers()

        async def waiter():
            try:
                await asyncio.sleep(self.idle_timeout)
                vc = text_channel.guild.voice_client
                if not vc:
                    return
                if reason == "no-music":
                    # Disconnect if still not playing
                    if not vc.is_playing() and not self.queue and not self.current:
                        await text_channel.send("🕒 No music for 5 minutes — disconnecting.")
                        await self._disconnect_cleanup(vc, clear_queue=False)
                elif reason == "empty-vc":
                    # Disconnect if still empty
                    if vc.channel and len([m for m in vc.channel.members if not m.bot]) == 0:
                        await text_channel.send("🚪 No listeners for 5 minutes — disconnecting.")
                        await self._disconnect_cleanup(vc, clear_queue=False)
            except asyncio.CancelledError:
                pass

        self.voice_cleanup_task = self.bot.loop.create_task(waiter())

    async def cancel_idle_timers(self):
        if self.voice_cleanup_task and not self.voice_cleanup_task.done():
            self.voice_cleanup_task.cancel()
        if self.empty_vc_task and not self.empty_vc_task.done():
            self.empty_vc_task.cancel()
        self.voice_cleanup_task = None
        self.empty_vc_task = None

    async def _disconnect_cleanup(self, vc: discord.VoiceClient, *, clear_queue: bool = True):
        try:
            if vc.is_playing():
                vc.stop()
        except Exception:
            pass
        await vc.disconnect()
        if clear_queue:
            self.queue.clear()
        self.current = None
        await self.cancel_idle_timers()

    async def enqueue(self, query: str, requester, text_channel: discord.abc.Messageable) -> Track:
        track = await fetch_track(query, requester)
        self.queue.append(track)
        await self.announce_enqueued(text_channel, track)
        return track

    # --------------- announcements ---------------
    async def announce_enqueued(self, channel: discord.abc.Messageable, track: Track):
        embed = discord.Embed(
            title=track.title,
            url=track.webpage_url,
            description=f"Added to queue by {getattr(track.requester, 'mention', str(track.requester))}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Length", value=track.pretty_duration(), inline=True)
        pos = len(self.queue)
        embed.add_field(name="Position in queue", value=str(pos), inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await channel.send(embed=embed)

    async def announce_now_playing(self, channel: discord.abc.Messageable, track: Track):
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

    async def announce_loop_toggle(self, channel: discord.abc.Messageable):
        state = "enabled" if self.loop_queue else "disabled"
        color = discord.Color.green() if self.loop_queue else discord.Color.red()
        embed = discord.Embed(title="Playlist Loop", description=f"Loop is now **{state}**.", color=color)
        await channel.send(embed=embed)

    # --------------- listeners ---------------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Only care about the bot's current guild/channel
        guild = member.guild
        vc = guild.voice_client
        if not vc or not vc.channel:
            return
        if before.channel == vc.channel or after.channel == vc.channel:
            # Check if channel is empty of non-bot users
            human_count = len([m for m in vc.channel.members if not m.bot])
            if human_count == 0:
                # start empty-vc timer
                text_channel = self._pick_announce_channel(guild)
                if text_channel:
                    await self.start_idle_timer(text_channel, reason="empty-vc")
            else:
                # cancel if someone is here
                await self.cancel_idle_timers()

    def _pick_announce_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        # Try to return a reasonable text channel to send announcements to
        # Prefer the system channel, else the first text channel the bot can speak in
        ch = getattr(guild, "system_channel", None)
        if ch and ch.permissions_for(guild.me).send_messages:
            return ch
        for c in guild.text_channels:
            if c.permissions_for(guild.me).send_messages:
                return c
        return None

    # --------------- commands ---------------
    async def _handle_play(self, voice_channel: discord.VoiceChannel, guild: discord.Guild, text_channel: discord.abc.Messageable, query: str, requester):
        await self.ensure_voice_for_context(voice_channel, guild)
        await self.enqueue(query, requester, text_channel)
        await self.start_playback_if_idle(guild, text_channel)

    # Prefix command
    @commands.command(name="play", help="Add a song to the queue (starts if idle)")
    async def play_cmd(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You are not connected to a voice channel.")
        await self._handle_play(ctx.author.voice.channel, ctx.guild, ctx.channel, query, ctx.author)

    # Slash command
    @app_commands.command(name="play", description="Add a song to the queue (starts if idle)")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("❌ You are not in a voice channel.", ephemeral=True)
        # Defer to allow yt-dlp fetch without timing out
        await interaction.response.defer(thinking=True)
        await self._handle_play(interaction.user.voice.channel, interaction.guild, interaction.channel, query, interaction.user)
        try:
            await interaction.followup.send("✅ Added to queue.")
        except discord.HTTPException:
            pass

    @commands.command(name="queue", help="Show the queue")
    async def queue_show(self, ctx: commands.Context):
        if not self.queue:
            return await ctx.send("(Queue is empty)")
        lines = []
        for i, t in enumerate(self.queue, start=1):
            lines.append(f"**{i}.** [{t.title}]({t.webpage_url}) — {t.pretty_duration()} • requested by {getattr(t.requester, 'mention', str(t.requester))}")
        embed = discord.Embed(title="Queue", description="\n".join(lines)[:4000], color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @app_commands.command(name="queue", description="Show the queue")
    async def slash_queue(self, interaction: discord.Interaction):
        if not self.queue:
            return await interaction.response.send_message("(Queue is empty)", ephemeral=True)
        lines = []
        for i, t in enumerate(self.queue, start=1):
            lines.append(f"**{i}.** [{t.title}]({t.webpage_url}) — {t.pretty_duration()} • requested by {getattr(t.requester, 'mention', str(t.requester))}")
        embed = discord.Embed(title="Queue", description="\n".join(lines)[:4000], color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)

    @commands.command(name="skip", help="Skip the current song")
    async def skip(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def slash_skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.")

    @commands.command(name="stop", help="Stop and disconnect")
    async def stop(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc:
            await self._disconnect_cleanup(vc)
            await ctx.send("🛑 Stopped and left the channel.")
        else:
            await ctx.send("❌ Not connected.")

    @app_commands.command(name="stop", description="Stop and disconnect")
    async def slash_stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await self._disconnect_cleanup(vc)
            await interaction.response.send_message("🛑 Stopped and left the channel.")
        else:
            await interaction.response.send_message("❌ Not connected.")

    @commands.command(name="pause", help="Pause playback")
    async def pause(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @app_commands.command(name="pause", description="Pause playback")
    async def slash_pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.")

    @commands.command(name="resume", help="Resume playback")
    async def resume(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @app_commands.command(name="resume", description="Resume playback")
    async def slash_resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.")

    @commands.command(name="nowplaying", aliases=["np"], help="Show current track")
    async def nowplaying(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()) and self.current:
            await self.announce_now_playing(ctx.channel, self.current)
        else:
            await ctx.send("❌ Nothing is playing.")

    @app_commands.command(name="nowplaying", description="Show current track")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()) and self.current:
            await interaction.response.send_message(embed=discord.Embed(title="Now Playing", description=f"[{self.current.title}]({self.current.webpage_url}) • {self.current.pretty_duration()}", color=discord.Color.green()))
        else:
            await interaction.response.send_message("❌ Nothing is playing.")

    @commands.command(name="loop", help="Toggle playlist loop")
    async def loop_(self, ctx: commands.Context):
        self.loop_queue = not self.loop_queue
        await self.announce_loop_toggle(ctx.channel)

    @app_commands.command(name="loop", description="Toggle playlist loop")
    async def slash_loop(self, interaction: discord.Interaction):
        self.loop_queue = not self.loop_queue
        await interaction.response.send_message(f"Loop is now {'enabled' if self.loop_queue else 'disabled'}.")
        # Also send the nicer embed announcement to channel
        await self.announce_loop_toggle(interaction.channel)

    # ======================
    # SHUFFLE
    # ======================
    @commands.command(name="shuffle")
    async def shuffle_(self, ctx):
        if not self.queue:
            await ctx.send("❌ The queue is empty, nothing to shuffle.")
            return

        random.shuffle(self.queue)
        await ctx.send("🔀 The queue has been shuffled!")

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def slash_shuffle(self, interaction: discord.Interaction):
        if not self.queue:
            await interaction.response.send_message("❌ The queue is empty, nothing to shuffle.")
            return

        random.shuffle(self.queue)
        await interaction.response.send_message("🔀 The queue has been shuffled!")



# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
