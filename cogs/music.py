import asyncio
import time
from dataclasses import dataclass
from typing import Deque, Optional, List
from collections import deque

import discord
from discord.ext import commands, tasks
from discord import app_commands
import yt_dlp

# ---- yt-dlp & ffmpeg tuning ----
BASE_YTDL = {
    "format": "bestaudio/best",
    "nocheckcertificate": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cachedir": False,
    "geo_bypass": True,
}

FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin"
FFMPEG_OPTS   = "-vn -ar 48000 -ac 2 -b:a 192k -loglevel warning"

ytdl_full = yt_dlp.YoutubeDL(BASE_YTDL.copy())  # single videos
# use flat extraction for big playlists → fast enqueue, resolve per-track at play time
ytdl_flat = yt_dlp.YoutubeDL({**BASE_YTDL, "extract_flat": "in_playlist"})

@dataclass
class Track:
    title: str
    webpage_url: str
    requester: discord.abc.User
    thumbnail: Optional[str] = None
    # stream_url resolved lazily when we actually play:
    stream_url: Optional[str] = None

    async def resolve_stream(self, loop: asyncio.AbstractEventLoop):
        if self.stream_url:
            return self.stream_url

        def _extract():
            data = ytdl_full.extract_info(self.webpage_url, download=False)
            # choose direct URL from the bestaudio format
            return data.get("url"), data

        url, data = await loop.run_in_executor(None, _extract)
        self.stream_url = url
        if not self.thumbnail:
            self.thumbnail = data.get("thumbnail")
        if not self.title:
            self.title = data.get("title") or "Unknown Title"
        return self.stream_url


class MusicPlayer:
    """Per-guild music state + player loop."""
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.text_channel: Optional[discord.abc.Messageable] = None

        self.queue: Deque[Track] = deque()
        self.current: Optional[Track] = None
        self.loop_mode: str = "off"  # off | one | all

        self._play_task: Optional[asyncio.Task] = None
        self._wake = asyncio.Event()

        # timers for afk logic
        self._last_active = time.time()
        self._alone_since: Optional[float] = None

    # ---- helpers ----
    def voice(self) -> Optional[discord.VoiceClient]:
        return self.guild.voice_client

    def mark_active(self):
        self._last_active = time.time()

    def is_alone(self) -> bool:
        vc = self.voice()
        if not vc or not vc.channel:
            return False
        humans = [m for m in vc.channel.members if not m.bot]
        return len(humans) == 0

    async def send(self, content=None, **kwargs):
        if self.text_channel:
            try:
                return await self.text_channel.send(content, **kwargs)
            except discord.HTTPException:
                pass

    # ---- connection ----
    async def ensure_connected(self, channel: discord.VoiceChannel):
        vc = self.voice()
        if vc is None:
            await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)
        self.mark_active()

        # start loop if stopped
        if not self._play_task or self._play_task.done():
            self._play_task = self.bot.loop.create_task(self.player_loop())

    # ---- queue ops ----
    def enqueue(self, tracks: List[Track]):
        for t in tracks:
            self.queue.append(t)
        self.mark_active()
        self._wake.set()

    # ---- core loop ----
    async def player_loop(self):
        await asyncio.sleep(0)
        announced_idle = False

        while True:
            # AFK checks (5 min alone OR 5 min idle)
            await self._check_afk()

            if not self.current:
                # nothing playing; pick next
                if not self.queue:
                    if not announced_idle:
                        await self.send("🛑 Music stopped, nothing playing.")
                        announced_idle = True
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=10.0)
                    except asyncio.TimeoutError:
                        continue
                    finally:
                        self._wake.clear()
                    continue

                announced_idle = False
                self.current = self.queue.popleft()
                self.mark_active()

                try:
                    stream = await self.current.resolve_stream(self.bot.loop)
                except Exception as e:
                    await self.send(f"⚠️ Failed to load **{self.current.title}**: `{e}`")
                    self.current = None
                    continue

                vc = self.voice()
                if not vc:
                    self.current = None
                    continue

                source = discord.FFmpegPCMAudio(
                    stream,
                    before_options=FFMPEG_BEFORE,
                    options=FFMPEG_OPTS
                )
                source = discord.PCMVolumeTransformer(source, volume=0.5)

                end_evt = asyncio.Event()

                def _after(err):
                    if err:
                        print(f"[after] {err}")
                    self.bot.loop.call_soon_threadsafe(end_evt.set)

                vc.play(source, after=_after)

                # Announce
                embed = discord.Embed(
                    title="🎶 Now Playing",
                    description=f"**{self.current.title}**",
                    color=discord.Color.green()
                )
                if self.current.thumbnail:
                    embed.set_thumbnail(url=self.current.thumbnail)
                embed.add_field(name="Requested by", value=self.current.requester.mention, inline=True)
                embed.add_field(name="Loop", value=self.loop_mode, inline=True)
                if hasattr(self.current, "webpage_url") and self.current.webpage_url:
                    embed.add_field(name="Link", value=self.current.webpage_url, inline=False)
                await self.send(embed=embed)

                await end_evt.wait()

                # Re-queue logic (append current at end if loop all; replay if loop one)
                finished = self.current
                self.current = None

                if self.loop_mode == "one":
                    # put back to the front to replay immediately
                    self.queue.appendleft(finished)
                elif self.loop_mode == "all":
                    # append to end to cycle the playlist (even if user skipped)
                    self.queue.append(finished)
                    # Announce Loop
                if len(self.queue) == len(self.original_queue):
                    # means why cycled through everything 
                    try:
                        await self.text_channel.send("🔁 Playlist looprr successfully.")
                    except Exception:
                        pass

                self._wake.set()
                continue

            await asyncio.sleep(0.05)

    async def _chec   vc = self.voice()
        if not vc:
            return

        # Alone tracking
        if self.is_alone():
            if self._alone_since is None:
                self._alone_since = time.time()
        else:
            self._alone_since = None

        now = time.time()

        # Alone 5 minutes
        if self._alone_since and (now - self._alone_since) >= 300:
            await self.send("👋 I’ve been alone for 5 minutes, disconnecting.")
            await self._disconnect()
            return

        # Idle (no current & empty queue) for 5 minutes
        if not self.current and not self.queue and (now - self._last_active) >= 300:
            await self.send("⏱️ No music for 5 minutes, disconnecting.")
            await self._disconnect()
            return

    async def _disconnect(self):
        vc = self.voice()
        if vc:
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass
        self.queue.clear()
        self.current = None

# ---------------- Cog ----------------
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}
        self.guard_loop.start()

    def cog_unload(self):
        self.guard_loop.cancel()

    def player(self, guild: discord.Guild) -> MusicPlayer:
        p = self.players.get(guild.id)
        if not p:
            p = MusicPlayer(self.bot, guild)
            self.players[guild.id] = p
        return p

    # -------- background safety: keep text channel alive --------
    @tasks.loop(minutes=2)
    async def guard_loop(self):
        # keep alive; nothing heavy here
        pass

    @guard_loop.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    # -------- helpers --------
    async def _connect_to_invoker(self, ctx_or_inter):
        if isinstance(ctx_or_inter, commands.Context):
            member = ctx_or_inter.author
            channel = member.voice.channel if member.voice else None
            text = ctx_or_inter.channel
            guild = ctx_or_inter.guild
        else:
            member = ctx_or_inter.user
            channel = member.voice.channel if getattr(member, "voice", None) else None
            text = ctx_or_inter.channel
            guild = ctx_or_inter.guild

        if not channel:
            raise commands.CommandError("❌ You must be in a voice channel.")
        pl = self.player(guild)
        pl.text_channel = text
        await pl.ensure_connected(channel)
        return pl

    async def _extract_tracks(self, query: str, requester: discord.abc.User) -> List[Track]:
        loop = asyncio.get_running_loop()

        def _extract():
            # Try flat first (fast for playlists/search)
            return ytdl_flat.extract_info(query, download=False)

        data = await loop.run_in_executor(None, _extract)

        tracks: List[Track] = []

        if "entries" in data and data["entries"]:
            for e in data["entries"]:
                if not e:
                    continue
                # flat entries often have 'url' as video id or full link
                web = e.get("url") or e.get("webpage_url")
                if web and not web.startswith("http"):
                    web = f"https://www.youtube.com/watch?v={web}"
                title = e.get("title") or "Unknown Title"
                thumb = (e.get("thumbnail")
                         or (e.get("thumbnails")[0]["url"] if e.get("thumbnails") else None))
                if web:
                    tracks.append(Track(title=title, webpage_url=web, requester=requester, thumbnail=thumb))
        else:
            # single video (non-flat)
            # In rare cases flat returns only id for single; resolve fully:
            def _extract_single():
                return ytdl_full.extract_info(query, download=False)
            d2 = data if data.get("webpage_url") else await loop.run_in_executor(None, _extract_single)
            web = d2.get("webpage_url") or d2.get("original_url") or d2.get("url")
            title = d2.get("title") or "Unknown Title"
            thumb = d2.get("thumbnail")
            if web:
                tracks.append(Track(title=title, webpage_url=web, requester=requester, thumbnail=thumb))

        return tracks

    # ---------------- Commands ----------------
    # PLAY
    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        await ctx.trigger_typing()
        pl = await self._connect_to_invoker(ctx)
        tracks = await self._extract_tracks(query, requester=ctx.author)
        if not tracks:
            return await ctx.reply("❌ Couldn't find anything.")
        pl.enqueue(tracks)
        await ctx.reply(f"✅ Added **{len(tracks)}** track(s).")
    
    @app_commands.command(name="play", description="Play a song or a playlist (search or URL)")
    @app_commands.describe(query="Search terms or a YouTube URL/playlist URL")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        pl = await self._connect_to_invoker(interaction)
        tracks = await self._extract_tracks(query, requester=interaction.user)
        if not tracks:
            return await interaction.followup.send("❌ Couldn't find anything.")
        pl.enqueue(tracks)
        await interaction.followup.send(f"✅ Added **{len(tracks)}** track(s).")

    # QUEUE
    @commands.command(name="queue", aliases=["q"])
    async def queue_prefix(self, ctx: commands.Context):
        await self._show_queue(ctx.channel, ctx.guild)

    @app_commands.command(name="queue", description="Show the queue")
    async def queue_slash(self, interaction: discord.Interaction):
        await self._show_queue(interaction.channel, interaction.guild)
        await interaction.response.send_message("📜 Sent the queue here.", ephemeral=True)

    async def _show_queue(self, channel: discord.abc.Messageable, guild: discord.Guild):
        pl = self.player(guild)
        desc = ""
        if pl.current:
            desc += f"**Now:** {pl.current.title}\n\n"
        if pl.queue:
            for i, t in enumerate(list(pl.queue)[:15], start=1):
                desc += f"`{i}.` {t.title}\n"
            if len(pl.queue) > 15:
                desc += f"... and {len(pl.queue) - 15} more"
        else:
            if not pl.current:
                desc += "_Queue is empty._"
        embed = discord.Embed(title="Queue", description=desc or "_Queue is empty._", color=discord.Color.blurple())
        await channel.send(embed=embed)

    # NOW PLAYING
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx: commands.Context):
        await self._np_common(ctx)

    @app_commands.command(name="nowplaying", description="Show the currently playing track")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        await self._np_common(interaction, ephemeral=True)

    async def _np_common(self, ctx_or_inter, ephemeral: bool = False):
        pl = self.player(ctx_or_inter.guild)
        if not pl.current:
            msg = "🛑 Music stopped, nothing playing."
            if isinstance(ctx_or_inter, commands.Context):
                return await ctx_or_inter.reply(msg)
            return await ctx_or_inter.response.send_message(msg, ephemeral=True)
        t = pl.current
        embed = discord.Embed(title="Now Playing", description=f"**{t.title}**", color=discord.Color.green())
        if t.thumbnail:
            embed.set_thumbnail(url=t.thumbnail)
        embed.add_field(name="Requested by", value=t.requester.mention, inline=True)
        if t.webpage_url:
            embed.add_field(name="Link", value=t.webpage_url, inline=False)
        if isinstance(ctx_or_inter, commands.Context):
            await ctx_or_inter.reply(embed=embed)
        else:
            await ctx_or_inter.response.send_message(embed=embed, ephemeral=ephemeral)

    # LOOP
    LOOP_CHOICES = [
    app_commands.Choice(name="off", value="off"),
    app_commands.Choice(name="one", value="one"),
    app_commands.Choice(name="all", value="all"),
]

# Prefix command
@commands.command(name="loop")
async def loop_prefix(self, ctx: commands.Context, mode: str = "off"):
    mode = mode.lower()
    if mode not in {"off", "one", "all"}:
        return await ctx.reply("❌ Choose `off`, `one`, or `all`.")

    self.player(ctx.guild).loop_mode = mode
    msg = f"🔁 Loop mode set to **{mode}**"
    if mode == "all":
        msg += "\n(Playlist will restart when it finishes — I’ll announce when it loops)"
    await ctx.reply(msg)

# Slash command
@app_commands.command(name="loop", description="Set loop mode")
@app_commands.choices(mode=LOOP_CHOICES)
async def loop_slash(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
    self.player(interaction.guild).loop_mode = mode.value
    msg = f"🔁 Loop mode set to **{mode.value}**"
    if mode.value == "all":
        msg += "\n(Playlist will restart when it finishes — I’ll announce when it loops)"
    await interaction.response.send_message(msg)
    # CONTROLS
    @commands.command(name="skip")
    async def skip_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.reply("⏭️ Skipped.")
        else:
            await ctx.reply("Nothing to skip.")

    @app_commands.command(name="skip", description="Skip the current track")
    async def skip_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)

    @commands.command(name="pause")
    async def pause_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.reply("⏸️ Paused.")
        else:
            await ctx.reply("Nothing is playing.")

    @app_commands.command(name="pause", description="Pause playback")
    async def pause_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @commands.command(name="resume")
    async def resume_prefix(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.reply("▶️ Resumed.")
        else:
            await ctx.reply("Nothing is paused.")

    @app_commands.command(name="resume", description="Resume playback")
    async def resume_slash(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is paused.", ephemeral=True)

    @commands.command(name="stop")
    async def stop_prefix(self, ctx: commands.Context):
        await self._stop_common(ctx.guild)
        await ctx.reply("🛑 Stopped and disconnected.")

    @app_commands.command(name="stop", description="Stop and disconnect")
    async def stop_slash(self, interaction: discord.Interaction):
        await self._stop_common(interaction.guild)
        await interaction.response.send_message("🛑 Stopped and disconnected.", ephemeral=True)

    async def _stop_common(self, guild: discord.Guild):
        pl = self.player(guild)
        pl.queue.clear()
        pl.current = None
        vc = guild.voice_client
        if vc:
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
