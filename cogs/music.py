# cogs/music.py
import asyncio
import time
from dataclasses import dataclass
from typing import Deque, Optional, List, Tuple
from collections import deque

import discord
from discord.ext import commands, tasks
from discord import app_commands
import yt_dlp


# ----------------------------- yt-dlp / ffmpeg setup -----------------------------
YTDL_OPTS_BASE = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cachedir": False,
    "geo_bypass": True,
}

# One full instance for precise (single) resolves, and one flat for fast playlist parsing
ytdl_full = yt_dlp.YoutubeDL({**YTDL_OPTS_BASE})
ytdl_flat = yt_dlp.YoutubeDL({**YTDL_OPTS_BASE, "extract_flat": "in_playlist"})

FFMPEG_BEFORE = "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
# Avoid copy; force decode/encode for stability; add a small buffer
FFMPEG_OPTS = "-vn -ar 48000 -ac 2 -b:a 192k -bufsize 16M -loglevel warning"


# ------------------------------------ Models -------------------------------------
@dataclass
class Track:
    title: str
    webpage_url: str
    requester: discord.abc.User
    thumbnail: Optional[str] = None
    stream_url: Optional[str] = None  # resolved right before play

    async def resolve_stream(self, loop: asyncio.AbstractEventLoop) -> str:
        """Fetch a direct audio URL for ffmpeg to consume."""
        if self.stream_url:
            return self.stream_url

        def _extract() -> Tuple[str, dict]:
            data = ytdl_full.extract_info(self.webpage_url, download=False)
            return data.get("url"), data

        url, data = await loop.run_in_executor(None, _extract)
        self.stream_url = url
        # backfill missing meta if needed
        self.thumbnail = self.thumbnail or data.get("thumbnail")
        self.title = self.title or data.get("title") or "Unknown Title"
        return self.stream_url


# --------------------------------- Player State ----------------------------------
class MusicPlayer:
    """Per-guild music player & queue."""
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.text_channel: Optional[discord.abc.Messageable] = None

        self.queue: Deque[Track] = deque()
        self.current: Optional[Track] = None
        self.loop_mode: str = "off"   # off | one | all

        self._play_task: Optional[asyncio.Task] = None
        self._wake = asyncio.Event()

        # AFK bookkeeping
        self._last_active = time.time()
        self._alone_since: Optional[float] = None

        # Loop cycle announcement bookkeeping (for loop=all)
        self._cycle_expected = 0
        self._cycle_progress = 0

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

        if not self._play_task or self._play_task.done():
            self._play_task = self.bot.loop.create_task(self.player_loop())

    # ---- queue ops ----
    def enqueue(self, tracks: List[Track]):
        for t in tracks:
            self.queue.append(t)
        self.mark_active()
        self._wake.set()

        # If we’re in loop=all and nothing is currently playing, snapshot cycle size for announcement.
        if self.loop_mode == "all" and self.current is None:
            # current will be taken from queue shortly; account for it in expected size
            self._cycle_expected = len(self.queue)
            self._cycle_progress = 0

    # ---- core loop ----
    async def player_loop(self):
        await asyncio.sleep(0)  # yield
        announced_idle = False

        while True:
            # AFK checks
            await self._check_afk()

            if not self.current:
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

                # If loop=all and we just started a new “cycle”, snapshot expected size
                if self.loop_mode == "all" and self._cycle_expected == 0:
                    self._cycle_expected = len(self.queue) + 1  # + current
                    self._cycle_progress = 0

                try:
                    stream = await self.current.resolve_stream(self.bot.loop)
                except Exception as e:
                    await self.send(f"⚠️ Failed to load **{self.current.title or 'Unknown'}**: `{e}`")
                    self.current = None
                    continue

                vc = self.voice()
                if not vc:
                    self.current = None
                    continue

                source = discord.FFmpegPCMAudio(
                    stream,
                    before_options=FFMPEG_BEFORE,
                    options=FFMPEG_OPTS,
                )
                source = discord.PCMVolumeTransformer(source, volume=0.5)

                end_evt = asyncio.Event()

                def _after(err):
                    if err:
                        # Log but never raise into discord.py loop
                        print(f"[ffmpeg after] {err}")
                    self.bot.loop.call_soon_threadsafe(end_evt.set)

                vc.play(source, after=_after)

                # Announce now playing
                embed = discord.Embed(
                    title="🎶 Now Playing",
                    description=f"**{self.current.title}**",
                    color=discord.Color.green(),
                )
                if self.current.thumbnail:
                    embed.set_thumbnail(url=self.current.thumbnail)
                embed.add_field(name="Requested by", value=self.current.requester.mention, inline=True)
                embed.add_field(name="Loop", value=self.loop_mode, inline=True)
                if getattr(self.current, "webpage_url", None):
                    embed.add_field(name="Link", value=self.current.webpage_url, inline=False)
                await self.send(embed=embed)

                await end_evt.wait()

                # Track finished
                finished = self.current
                self.current = None

                # Handle loop modes
                if self.loop_mode == "one":
                    self.queue.appendleft(finished)
                elif self.loop_mode == "all":
                    self.queue.append(finished)
                    # Cycle announcement bookkeeping
                    self._cycle_progress += 1
                    # If users added tracks mid-cycle, expand expectation
                    if self._cycle_progress > self._cycle_expected:
                        self._cycle_expected = self._cycle_progress
                    if self._cycle_expected and self._cycle_progress >= self._cycle_expected:
                        try:
                            await self.send("🔁 Playlist looped successfully.")
                        except Exception:
                            pass
                        # Reset for next cycle
                        self._cycle_progress = 0
                        self._cycle_expected = len(self.queue)  # next cycle size (current became last)

                else:
                    # loop off
                    self._cycle_progress = 0
                    self._cycle_expected = 0

                self._wake.set()
                continue

            await asyncio.sleep(0.05)

    # ---- AFK & housekeeping ----
    async def _check_afk(self):
        now = time.time()

        # Alone tracking
        if self.is_alone():
            if self._alone_since is None:
                self._alone_since = now
        else:
            self._alone_since = None

        # Alone for 5 minutes → disconnect
        if self._alone_since and (now - self._alone_since) >= 300:
            await self.send("👋 I’ve been alone for 5 minutes, disconnecting.")
            await self._disconnect()
            return

        # Idle (nothing playing & empty queue) for 5 minutes → disconnect
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
        self._cycle_progress = 0
        self._cycle_expected = 0


# ------------------------------------- Cog ---------------------------------------
class Music(commands.Cog):
    """Prefix + Slash music cog with robust play and loop announcement."""

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

    # ---------------- background keepalive (cheap) ----------------
    @tasks.loop(minutes=2)
    async def guard_loop(self):
        pass

    @guard_loop.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    # ---------------- helpers ----------------
    async def _connect_to_invoker(self, ctx_or_inter):
        """Join/move to the invoker's voice channel, set text channel, return player or None if not in VC."""
        # Resolve context fields
        if isinstance(ctx_or_inter, commands.Context):
            member = ctx_or_inter.author
            channel = member.voice.channel if member.voice else None
            text = ctx_or_inter.channel
            guild = ctx_or_inter.guild
            reply = ctx_or_inter.reply
        else:
            member = ctx_or_inter.user
            channel = member.voice.channel if getattr(member, "voice", None) else None
            text = ctx_or_inter.channel
            guild = ctx_or_inter.guild
            reply = None

        if not channel:
            # Do NOT raise; return a user-facing message so $play never bubbles an exception
            if isinstance(ctx_or_inter, commands.Context):
                await reply("❌ You must be in a voice channel.")
            else:
                await ctx_or_inter.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
            return None

        pl = self.player(guild)
        pl.text_channel = text
        await pl.ensure_connected(channel)
        return pl

    async def _extract_tracks(self, query: str, requester: discord.abc.User) -> List[Track]:
        """Robust search that handles URLs, playlists, and plain text."""
        loop = asyncio.get_running_loop()

        def _extract_flat_first():
            return ytdl_flat.extract_info(query, download=False)

        try:
            data = await loop.run_in_executor(None, _extract_flat_first)
        except Exception:
            # Fallback: force a ytsearch if the first pass failed (e.g., odd input)
            def _search1():
                return ytdl_full.extract_info(f"ytsearch1:{query}", download=False)
            data = await loop.run_in_executor(None, _search1)

        tracks: List[Track] = []

        # Case 1: Playlist or multi-entry search (flat or full)
        if isinstance(data, dict) and data.get("entries"):
            for e in data["entries"]:
                if not e:
                    continue
                web = e.get("webpage_url") or e.get("url")
                if web and not str(web).startswith("http"):
                    web = f"https://www.youtube.com/watch?v={web}"
                title = e.get("title") or "Unknown Title"
                thumb = e.get("thumbnail")
                if not thumb:
                    thumbs = e.get("thumbnails") or []
                    if thumbs:
                        thumb = thumbs[0].get("url")
                if web:
                    tracks.append(Track(title=title, webpage_url=web, requester=requester, thumbnail=thumb))

            if tracks:
                return tracks

        # Case 2: Single video or last-resort first entry
        # If the flat data didn't give us entries, try full extraction
        def _extract_full():
            return ytdl_full.extract_info(query, download=False)

        try:
            d2 = data if (isinstance(data, dict) and data.get("webpage_url")) else await loop.run_in_executor(None, _extract_full)
        except Exception:
            return []

        if isinstance(d2, dict):
            # A ytsearch result with entries
            if d2.get("entries"):
                e0 = next((x for x in d2["entries"] if x), None)
                if e0:
                    web = e0.get("webpage_url") or e0.get("url")
                    if web and not str(web).startswith("http"):
                        web = f"https://www.youtube.com/watch?v={web}"
                    title = e0.get("title") or "Unknown Title"
                    thumb = e0.get("thumbnail")
                    tracks.append(Track(title=title, webpage_url=web, requester=requester, thumbnail=thumb))
            else:
                web = d2.get("webpage_url") or d2.get("original_url") or d2.get("url")
                title = d2.get("title") or "Unknown Title"
                thumb = d2.get("thumbnail")
                if web:
                    tracks.append(Track(title=title, webpage_url=web, requester=requester, thumbnail=thumb))

        return tracks

    # -------------------------------- Commands (Prefix + Slash) --------------------------------
    # PLAY
    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        try:
            await ctx.trigger_typing()
            pl = await self._connect_to_invoker(ctx)
            if not pl:
                return
            tracks = await self._extract_tracks(query, requester=ctx.author)
            if not tracks:
                return await ctx.reply("❌ Couldn't find anything.")
            pl.enqueue(tracks)
            await ctx.reply(f"✅ Added **{len(tracks)}** track(s).")
        except Exception as e:
            # swallow & show friendly
            await ctx.reply(f"❌ Couldn't play that. ({e.__class__.__name__})")

    @app_commands.command(name="play", description="Play a song or a playlist (search or URL)")
    @app_commands.describe(query="Search terms or a YouTube URL/playlist URL")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        try:
            await interaction.response.defer(thinking=True)
            pl = await self._connect_to_invoker(interaction)
            if not pl:
                return
            tracks = await self._extract_tracks(query, requester=interaction.user)
            if not tracks:
                return await interaction.followup.send("❌ Couldn't find anything.")
            pl.enqueue(tracks)
            await interaction.followup.send(f"✅ Added **{len(tracks)}** track(s).")
        except Exception as e:
            await interaction.followup.send(f"❌ Couldn't play that. ({e.__class__.__name__})", ephemeral=True)

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
        embed = discord.Embed(
            title="Queue",
            description=desc or "_Queue is empty._",
            color=discord.Color.blurple()
        )
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
        embed = discord.Embed(
            title="Now Playing",
            description=f"**{t.title}**",
            color=discord.Color.green()
        )
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

    @commands.command(name="loop")
    async def loop_prefix(self, ctx: commands.Context, mode: str = "off"):
        mode = (mode or "off").lower()
        if mode not in {"off", "one", "all"}:
            return await ctx.reply("❌ Choose `off`, `one`, or `all`.")
        pl = self.player(ctx.guild)
        pl.loop_mode = mode
        # reset cycle counters when switching modes
        pl._cycle_progress = 0
        pl._cycle_expected = 0
        msg = f"🔁 Loop mode set to *
