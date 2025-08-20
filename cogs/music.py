import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import yt_dlp
import time
from collections import deque

# YTDLP config
ytdlp_format_options = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": False,
    "extract_flat": "in_playlist",
}
ytdlp = yt_dlp.YoutubeDL(ytdlp_format_options)


class Track:
    def __init__(self, source, title, url, thumbnail, requester):
        self.source = source
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.requester = requester


class MusicPlayer:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue = deque()
        self.current: Track | None = None
        self.voice: discord.VoiceClient | None = None
        self.loop_mode = "off"  # off, one, all
        self._alone_since = None
        self._idle_since = None

    async def connect(self, channel: discord.VoiceChannel):
        if self.voice and self.voice.is_connected():
            return self.voice
        self.voice = await channel.connect()
        return self.voice

    def add_track(self, track: Track):
        self.queue.append(track)

    async def play_next(self, ctx_or_inter=None):
        if self.loop_mode == "one" and self.current:
            self.queue.appendleft(self.current)
        elif self.loop_mode == "all" and self.current:
            self.queue.append(self.current)

        if not self.queue:
            self.current = None
            if ctx_or_inter:
                await self._safe_send(ctx_or_inter, "⏹️ Music stopped, nothing playing.")
            self._idle_since = time.time()
            return

        self.current = self.queue.popleft()
        source = discord.FFmpegPCMAudio(self.current.source, before_options="-nostdin", options="-vn")

        def after_play(err):
            coro = self.play_next(ctx_or_inter)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

        self.voice.play(source, after=after_play)

        # Reset idle timer
        self._idle_since = None

        # Send now playing embed
        if ctx_or_inter:
            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"**[{self.current.title}]({self.current.url})**",
                color=discord.Color.green(),
            )
            if self.current.thumbnail:
                embed.set_thumbnail(url=self.current.thumbnail)
            embed.add_field(name="Requested by", value=self.current.requester.mention)
            await self._safe_send(ctx_or_inter, embed=embed)

    async def _safe_send(self, ctx_or_inter, content=None, embed=None):
        try:
            if isinstance(ctx_or_inter, commands.Context):
                await ctx_or_inter.send(content=content, embed=embed)
            else:
                if ctx_or_inter.response.is_done():
                    await ctx_or_inter.followup.send(content=content, embed=embed)
                else:
                    await ctx_or_inter.response.send_message(content=content, embed=embed)
        except Exception:
            pass

    def is_alone(self):
        if not self.voice or not self.voice.channel:
            return False
        members = [m for m in self.voice.channel.members if not m.bot]
        return len(members) == 0


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}
        self.cleanup.start()

    def cog_unload(self):
        self.cleanup.cancel()

    def get_player(self, guild: discord.Guild):
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self.bot, guild)
        return self.players[guild.id]

    async def extract_tracks(self, query, requester):
        try:
            info = ytdlp.extract_info(query, download=False)
        except Exception:
            return []

        tracks = []
        if "entries" in info:
            for e in info["entries"]:
                if not e:
                    continue
                tracks.append(
                    Track(
                        e["url"],
                        e.get("title", "Unknown"),
                        e.get("webpage_url"),
                        e.get("thumbnail"),
                        requester,
                    )
                )
        else:
            tracks.append(
                Track(
                    info["url"],
                    info.get("title", "Unknown"),
                    info.get("webpage_url"),
                    info.get("thumbnail"),
                    requester,
                )
            )
        return tracks

    # ---------------- PREFIX COMMANDS ---------------- #

    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        """Play a song (prefix version)."""
        player = self.get_player(ctx.guild)
        if not ctx.author.voice:
            return await ctx.reply("❌ You must be in a voice channel.")
        await player.connect(ctx.author.voice.channel)

        tracks = await self.extract_tracks(query, requester=ctx.author)
        if not tracks:
            return await ctx.reply("❌ Couldn't find anything.")

        for t in tracks:
            player.add_track(t)

        await ctx.reply(f"✅ Added **{len(tracks)}** track(s).")
        if not player.voice.is_playing():
            await player.play_next(ctx)

    @commands.command(name="skip")
    async def skip_prefix(self, ctx: commands.Context):
        player = self.get_player(ctx.guild)
        if not player.voice or not player.voice.is_playing():
            return await ctx.reply("❌ Nothing is playing.")
        player.voice.stop()
        await ctx.reply("⏭️ Skipped.")

    @commands.command(name="stop")
    async def stop_prefix(self, ctx: commands.Context):
        player = self.get_player(ctx.guild)
        if player.voice:
            await player.voice.disconnect()
            self.players.pop(ctx.guild.id, None)
        await ctx.reply("⏹️ Stopped and disconnected.")

    @commands.command(name="queue")
    async def queue_prefix(self, ctx: commands.Context):
        player = self.get_player(ctx.guild)
        if not player.queue:
            return await ctx.reply("📭 Queue is empty.")
        desc = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(player.queue)])
        embed = discord.Embed(title="📜 Queue", description=desc[:4096], color=discord.Color.blue())
        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx: commands.Context):
        player = self.get_player(ctx.guild)
        if not player.current:
            return await ctx.reply("❌ Nothing playing.")
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{player.current.title}]({player.current.url})**",
            color=discord.Color.green(),
        )
        if player.current.thumbnail:
            embed.set_thumbnail(url=player.current.thumbnail)
        await ctx.send(embed=embed)

    @commands.command(name="loop")
    async def loop_prefix(self, ctx: commands.Context, mode: str = "off"):
        player = self.get_player(ctx.guild)
        mode = mode.lower()
        if mode not in {"off", "one", "all"}:
            return await ctx.reply("❌ Choose `off`, `one`, or `all`.")
        player.loop_mode = mode
        msg = f"🔁 Loop mode set to **{mode}**"
        if mode == "all":
            msg += "\n(Playlist will repeat until stopped.)"
        await ctx.reply(msg)

    # ---------------- SLASH COMMANDS ---------------- #

    @app_commands.command(name="play", description="Play a song")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        player = self.get_player(interaction.guild)
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
        await player.connect(interaction.user.voice.channel)

        tracks = await self.extract_tracks(query, requester=interaction.user)
        if not tracks:
            return await interaction.response.send_message("❌ Couldn't find anything.", ephemeral=True)

        for t in tracks:
            player.add_track(t)

        await interaction.response.send_message(f"✅ Added **{len(tracks)}** track(s).")
        if not player.voice.is_playing():
            await player.play_next(interaction)

    @app_commands.command(name="skip", description="Skip current song")
    async def skip_slash(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.voice or not player.voice.is_playing():
            return await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        player.voice.stop()
        await interaction.response.send_message("⏭️ Skipped.")

    @app_commands.command(name="stop", description="Stop and disconnect")
    async def stop_slash(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if player.voice:
            await player.voice.disconnect()
            self.players.pop(interaction.guild.id, None)
        await interaction.response.send_message("⏹️ Stopped and disconnected.")

    @app_commands.command(name="queue", description="Show queue")
    async def queue_slash(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.queue:
            return await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
        desc = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(player.queue)])
        embed = discord.Embed(title="📜 Queue", description=desc[:4096], color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show current song")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.current:
            return await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{player.current.title}]({player.current.url})**",
            color=discord.Color.green(),
        )
        if player.current.thumbnail:
            embed.set_thumbnail(url=player.current.thumbnail)
        await interaction.response.send_message(embed=embed)

    LOOP_CHOICES = [
        app_commands.Choice(name="off", value="off"),
        app_commands.Choice(name="one", value="one"),
        app_commands.Choice(name="all", value="all"),
    ]

    @app_commands.command(name="loop", description="Set loop mode")
    @app_commands.choices(mode=LOOP_CHOICES)
    async def loop_slash(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        player = self.get_player(interaction.guild)
        player.loop_mode = mode.value
        msg = f"🔁 Loop mode set to **{mode.value}**"
        if mode.value == "all":
            msg += "\n(Playlist will repeat until stopped.)"
        await interaction.response.send_message(msg)

    # ---------------- AUTO CLEANUP ---------------- #

    @tasks.loop(seconds=30)
    async def cleanup(self):
        now = time.time()
        for guild_id, player in list(self.players.items()):
            if player.is_alone():
                if player._alone_since is None:
                    player._alone_since = now
                elif now - player._alone_since > 300:
                    await player.voice.disconnect()
                    self.players.pop(guild_id, None)
            else:
                player._alone_since = None

            if player._idle_since and now - player._idle_since > 300:
                if player.voice:
                    await player.voice.disconnect()
                self.players.pop(guild_id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
