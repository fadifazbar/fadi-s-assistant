import asyncio
import time
from collections import deque

import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp


# ----------- YTDL SETUP -----------
ytdl_format_options = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "default_search": "ytsearch",
    "extract_flat": "in_playlist",
}
ffmpeg_options = {"options": "-vn"}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


# ----------- TRACK -----------
class Track:
    def __init__(self, source, title, url, webpage_url, thumbnail, requester):
        self.source = source
        self.title = title
        self.url = url
        self.webpage_url = webpage_url
        self.thumbnail = thumbnail
        self.requester = requester


# ----------- PLAYER -----------
class MusicPlayer:
    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild
        self.queue = deque()
        self.current: Track | None = None
        self.voice: discord.VoiceClient | None = None
        self.loop_mode = "off"  # off, one, all
        self._task = bot.loop.create_task(self.player_loop())
        self._event = asyncio.Event()
        self._alone_since = None
        self._idle_since = None
        self._cycle_progress = 0
        self._cycle_expected = 0

    def is_connected(self):
        return self.voice and self.voice.is_connected()

    def enqueue(self, tracks):
        for t in tracks:
            self.queue.append(t)
        if not self._event.is_set():
            self._event.set()

    async def player_loop(self):
        while True:
            try:
                self._event.clear()

                # auto-disconnect if alone or idle 5 minutes
                if self.voice and self.voice.channel:
                    if self.is_alone():
                        if self._alone_since is None:
                            self._alone_since = time.time()
                        elif time.time() - self._alone_since >= 300:
                            await self.stop_and_disconnect()
                            return
                    else:
                        self._alone_since = None

                if not self.queue:
                    if self._idle_since is None:
                        self._idle_since = time.time()
                    elif time.time() - self._idle_since >= 300:
                        await self.stop_and_disconnect()
                        return
                    await self._event.wait()
                    continue
                else:
                    self._idle_since = None

                self.current = self.queue.popleft()
                source = discord.FFmpegPCMAudio(
                    self.current.url, **ffmpeg_options
                )
                self.voice.play(
                    source, after=lambda e: self.bot.loop.call_soon_threadsafe(self._event.set)
                )

                # announce now playing
                embed = discord.Embed(
                    title="Now Playing 🎶",
                    description=f"**[{self.current.title}]({self.current.webpage_url})**",
                    color=discord.Color.green(),
                )
                if self.current.thumbnail:
                    embed.set_thumbnail(url=self.current.thumbnail)
                embed.add_field(name="Requested by", value=self.current.requester.mention)
                try:
                    await self.guild.system_channel.send(embed=embed)
                except:
                    pass

                # wait for song to end
                while self.voice.is_playing() or self.voice.is_paused():
                    await asyncio.sleep(1)

                finished = self.current
                self.current = None

                # handle looping
                if self.loop_mode == "one":
                    self.queue.appendleft(finished)
                elif self.loop_mode == "all":
                    self.queue.append(finished)
                    self._cycle_progress += 1
                    if self._cycle_expected and self._cycle_progress >= self._cycle_expected:
                        self._cycle_progress = 0
                        await self.announce_cycle()

            except Exception as e:
                print(f"Player error: {e}")
                await asyncio.sleep(2)

    async def announce_cycle(self):
        try:
            await self.guild.system_channel.send("🔁 Playlist looped successfully.")
        except:
            pass

    async def stop_and_disconnect(self):
        if self.voice:
            await self.voice.disconnect()
        self.queue.clear()
        self.current = None
        self._event.set()

    def is_alone(self):
        if not self.voice or not self.voice.channel:
            return False
        return len(self.voice.channel.members) == 1


# ----------- COG -----------
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    def player(self, guild: discord.Guild):
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self.bot, guild)
        return self.players[guild.id]

    async def _connect(self, ctx_or_inter):
        if isinstance(ctx_or_inter, commands.Context):
            channel = ctx_or_inter.author.voice.channel
        else:
            channel = ctx_or_inter.user.voice.channel
        pl = self.player(ctx_or_inter.guild)
        if not pl.voice or not pl.is_connected():
            pl.voice = await channel.connect()
        return pl

    async def _extract_tracks(self, query, requester):
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        except Exception as e:
            print(f"ytdl error: {e}")
            return []
        if data is None:
            return []

        entries = []
        if "entries" in data:
            for e in data["entries"]:
                if not e:
                    continue
                entries.append(
                    Track(
                        e.get("url"),
                        e.get("title", "Unknown"),
                        e.get("url"),
                        e.get("webpage_url"),
                        e.get("thumbnail"),
                        requester,
                    )
                )
        else:
            entries.append(
                Track(
                    data.get("url"),
                    data.get("title", "Unknown"),
                    data.get("url"),
                    data.get("webpage_url"),
                    data.get("thumbnail"),
                    requester,
                )
            )
        return entries

    # ---------- COMMANDS ----------

    # --- Play ---
    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx, *, query: str):
        await ctx.trigger_typing()
        pl = await self._connect(ctx)
        tracks = await self._extract_tracks(query, requester=ctx.author)
        if not tracks:
            return await ctx.reply("❌ Couldn't find anything.")
        pl.enqueue(tracks)
        if len(tracks) == 1:
            await ctx.reply(f"✅ Added **{tracks[0].title}**")
        else:
            pl._cycle_expected = len(tracks)
            await ctx.reply(f"✅ Added **{len(tracks)}** tracks.")

    @app_commands.command(name="play", description="Play music")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        pl = await self._connect(interaction)
        tracks = await self._extract_tracks(query, requester=interaction.user)
        if not tracks:
            return await interaction.followup.send("❌ Couldn't find anything.")
        pl.enqueue(tracks)
        if len(tracks) == 1:
            await interaction.followup.send(f"✅ Added **{tracks[0].title}**")
        else:
            pl._cycle_expected = len(tracks)
            await interaction.followup.send(f"✅ Added **{len(tracks)}** tracks.")

    # --- Queue ---
    @commands.command(name="queue", aliases=["q"])
    async def queue_prefix(self, ctx):
        pl = self.player(ctx.guild)
        if not pl.queue and not pl.current:
            return await ctx.reply("❌ Queue is empty.")
        desc = ""
        if pl.current:
            desc += f"🎶 Now: **{pl.current.title}**\n"
        for i, t in enumerate(list(pl.queue)[:10], 1):
            desc += f"{i}. {t.title}\n"
        embed = discord.Embed(title="Queue", description=desc, color=discord.Color.blurple())
        await ctx.reply(embed=embed)

    @app_commands.command(name="queue", description="Show queue")
    async def queue_slash(self, interaction: discord.Interaction):
        pl = self.player(interaction.guild)
        if not pl.queue and not pl.current:
            return await interaction.response.send_message("❌ Queue is empty.")
        desc = ""
        if pl.current:
            desc += f"🎶 Now: **{pl.current.title}**\n"
        for i, t in enumerate(list(pl.queue)[:10], 1):
            desc += f"{i}. {t.title}\n"
        embed = discord.Embed(title="Queue", description=desc, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)

    # --- Pause ---
    @commands.command(name="pause")
    async def pause_prefix(self, ctx):
        pl = self.player(ctx.guild)
        if pl.voice and pl.voice.is_playing():
            pl.voice.pause()
            await ctx.reply("⏸️ Paused.")
        else:
            await ctx.reply("❌ Nothing is playing.")

    @app_commands.command(name="pause", description="Pause music")
    async def pause_slash(self, interaction: discord.Interaction):
        pl = self.player(interaction.guild)
        if pl.voice and pl.voice.is_playing():
            pl.voice.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.")

    # --- Resume ---
    @commands.command(name="resume")
    async def resume_prefix(self, ctx):
        pl = self.player(ctx.guild)
        if pl.voice and pl.voice.is_paused():
            pl.voice.resume()
            await ctx.reply("▶️ Resumed.")
        else:
            await ctx.reply("❌ Nothing is paused.")

    @app_commands.command(name="resume", description="Resume music")
    async def resume_slash(self, interaction: discord.Interaction):
        pl = self.player(interaction.guild)
        if pl.voice and pl.voice.is_paused():
            pl.voice.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.")

    # --- Skip ---
    @commands.command(name="skip")
    async def skip_prefix(self, ctx):
        pl = self.player(ctx.guild)
        if not pl.voice or not pl.voice.is_playing():
            return await ctx.reply("❌ Nothing is playing.")
        pl.voice.stop()
        await ctx.reply("⏭️ Skipped.")

    @app_commands.command(name="skip", description="Skip current track")
    async def skip_slash(self, interaction: discord.Interaction):
        pl = self.player(interaction.guild)
        if not pl.voice or not pl.voice.is_playing():
            return await interaction.response.send_message("❌ Nothing is playing.")
        pl.voice.stop()
        await interaction.response.send_message("⏭️ Skipped.")

    # --- Stop ---
    @commands.command(name="stop")
    async def stop_prefix(self, ctx):
        pl = self.player(ctx.guild)
        await pl.stop_and_disconnect()
        await ctx.reply("⏹️ Stopped and disconnected.")

    @app_commands.command(name="stop", description="Stop music")
    async def stop_slash(self, interaction: discord.Interaction):
        pl = self.player(interaction.guild)
        await pl.stop_and_disconnect()
        await interaction.response.send_message("⏹️ Stopped and disconnected.")

    # --- Loop ---
    @commands.command(name="loop")
    async def loop_prefix(self, ctx: commands.Context, mode: str = "off"):
        mode = (mode or "off").lower()
        if mode not in {"off", "one", "all"}:
            return await ctx.reply("❌ Choose `off`, `one`, or `all`.")
        pl = self.player(ctx.guild)
        pl.loop_mode = mode
        pl._cycle_progress = 0
        pl._cycle_expected = 0
        msg = f"🔁 Loop mode set to **{mode}**" if mode != "off" else "⏹️ Looping disabled."
        await ctx.reply(msg)

    LOOP_CHOICES = [
        app_commands.Choice(name="off", value="off"),
        app_commands.Choice(name="one", value="one"),
        app_commands.Choice(name="all", value="all"),
    ]

    @app_commands.command(name="loop", description="Set loop mode")
    @app_commands.choices(mode=LOOP_CHOICES)
    async def loop_slash(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        pl = self.player(interaction.guild)
        pl.loop_mode = mode.value
        pl._cycle_progress = 0
        pl._cycle_expected = 0
        msg = f"🔁 Loop mode set to **{mode.value}**" if mode.value != "off" else "⏹️ Looping disabled."
        await interaction.response.send_message(msg)


async def setup(bot):
    await bot.add_cog(Music(bot))
