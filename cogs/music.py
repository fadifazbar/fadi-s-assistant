import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
from collections import deque
import time

YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": False,
    "default_search": "ytsearch",
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


class Track:
    def __init__(self, info, requester):
        self.title = info.get("title")
        self.web_url = info.get("webpage_url")
        self.url = info["url"]
        self.duration = info.get("duration")
        self.thumbnail = info.get("thumbnail")
        self.requester = requester


class MusicPlayer:
    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild
        self.queue = deque()
        self.voice = None
        self.current = None
        self.play_next = asyncio.Event()
        self.looping = False
        self.start_time = None
        self.task = asyncio.create_task(self.loop())

    async def add(self, query, requester):
        data = await asyncio.to_thread(lambda: ytdl.extract_info(query, download=False))
        if "entries" in data:
            data = data["entries"][0]
        track = Track(data, requester)
        self.queue.append(track)
        return track

    async def connect(self, channel):
        if self.voice and self.voice.is_connected():
            await self.voice.move_to(channel)
        else:
            self.voice = await channel.connect()

    async def loop(self):
        while True:
            self.play_next.clear()

            if not self.queue:
                await asyncio.sleep(300)  # 5 min idle timeout
                if not self.queue and (not self.voice or not self.voice.is_playing()):
                    if self.voice:
                        await self.voice.disconnect()
                    return
                continue

            self.current = self.queue.popleft()
            self.start_time = time.time()

            source = await discord.FFmpegOpusAudio.from_probe(self.current.url, **FFMPEG_OPTS)
            self.voice.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.play_next.set))

            chan = self.voice.channel.guild.system_channel or discord.utils.get(self.guild.text_channels, permissions__send_messages=True)
            if chan:
                embed = self.make_embed("Now Playing", self.current, "🎶")
                await chan.send(embed=embed)

            await self.play_next.wait()

            if self.looping and self.current:
                self.queue.appendleft(self.current)

    def make_embed(self, title, track, emoji="🎵", show_progress=False):
        embed = discord.Embed(title=f"{emoji} {title}", description=f"[{track.title}]({track.web_url})", color=0x7289DA)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        embed.add_field(name="Requested by", value=track.requester.mention, inline=True)
        if track.duration:
            length = self.format_time(track.duration)
            if show_progress and self.start_time:
                elapsed = int(time.time() - self.start_time)
                bar = self.progress_bar(elapsed, track.duration)
                embed.add_field(name="Progress", value=f"{self.format_time(elapsed)} / {length}\n{bar}", inline=False)
            else:
                embed.add_field(name="Length", value=length, inline=True)
        return embed

    @staticmethod
    def format_time(seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @staticmethod
    def progress_bar(elapsed, total, length=15):
        filled = int(length * elapsed // total) if total else 0
        return "▓" * filled + "░" * (length - filled)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    def get_player(self, ctx_or_inter):
        guild = ctx_or_inter.guild
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self.bot, guild)
        return self.players[guild.id]

    # -------------- PREFIX COMMANDS --------------
    @commands.command(name="play")
    async def play_cmd(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You must be in a voice channel.")
        player = self.get_player(ctx)
        await player.connect(ctx.author.voice.channel)
        track = await player.add(query, ctx.author)
        embed = player.make_embed("Added to Queue", track, "➕")
        await ctx.send(embed=embed)

    @commands.command(name="skip")
    async def skip_cmd(self, ctx):
        player = self.get_player(ctx)
        if player.voice and player.voice.is_playing():
            player.voice.stop()
            await ctx.send("⏭️ Skipped.")

    @commands.command(name="pause")
    async def pause_cmd(self, ctx):
        player = self.get_player(ctx)
        if player.voice and player.voice.is_playing():
            player.voice.pause()
            await ctx.send("⏸️ Paused.")

    @commands.command(name="resume")
    async def resume_cmd(self, ctx):
        player = self.get_player(ctx)
        if player.voice and player.voice.is_paused():
            player.voice.resume()
            await ctx.send("▶️ Resumed.")

    @commands.command(name="stop")
    async def stop_cmd(self, ctx):
        player = self.get_player(ctx)
        if player.voice:
            player.queue.clear()
            await player.voice.disconnect()
            await ctx.send("🛑 Stopped and disconnected.")

    @commands.command(name="loop")
    async def loop_cmd(self, ctx):
        player = self.get_player(ctx)
        player.looping = not player.looping
        await ctx.send("🔁 Loop enabled." if player.looping else "➡️ Loop disabled.")

    @commands.command(name="queue")
    async def queue_cmd(self, ctx):
        player = self.get_player(ctx)
        if not player.queue:
            return await ctx.send("🎵 Queue is empty.")
        embed = discord.Embed(title="📜 Current Queue", color=0x00ffcc)
        for i, t in enumerate(list(player.queue)[:10], start=1):
            embed.add_field(name=f"{i}.", value=f"[{t.title}]({t.web_url}) • {t.requester.mention}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_cmd(self, ctx):
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send("❌ Nothing is playing right now.")
        embed = player.make_embed("Now Playing", player.current, "🎵", show_progress=True)
        await ctx.send(embed=embed)

    # -------------- SLASH COMMANDS --------------
    @app_commands.command(name="play", description="Play a song")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
        player = self.get_player(interaction)
        await player.connect(interaction.user.voice.channel)
        track = await player.add(query, interaction.user)
        embed = player.make_embed("Added to Queue", track, "➕")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="skip", description="Skip current song")
    async def slash_skip(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.voice and player.voice.is_playing():
            player.voice.stop()
            await interaction.response.send_message("⏭️ Skipped.")

    @app_commands.command(name="pause", description="Pause music")
    async def slash_pause(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.voice and player.voice.is_playing():
            player.voice.pause()
            await interaction.response.send_message("⏸️ Paused.")

    @app_commands.command(name="resume", description="Resume music")
    async def slash_resume(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.voice and player.voice.is_paused():
            player.voice.resume()
            await interaction.response.send_message("▶️ Resumed.")

    @app_commands.command(name="stop", description="Stop and disconnect")
    async def slash_stop(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.voice:
            player.queue.clear()
            await player.voice.disconnect()
            await interaction.response.send_message("🛑 Stopped and disconnected.")

    @app_commands.command(name="loop", description="Toggle loop")
    async def slash_loop(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        player.looping = not player.looping
        await interaction.response.send_message("🔁 Loop enabled." if player.looping else "➡️ Loop disabled.")

    @app_commands.command(name="queue", description="Show queue")
    async def slash_queue(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if not player.queue:
            return await interaction.response.send_message("🎵 Queue is empty.")
        embed = discord.Embed(title="📜 Current Queue", color=0x00ffcc)
        for i, t in enumerate(list(player.queue)[:10], start=1):
            embed.add_field(name=f"{i}.", value=f"[{t.title}]({t.web_url}) • {t.requester.mention}", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the currently playing track")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if not player.current:
            return await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
        embed = player.make_embed("Now Playing", player.current, "🎵", show_progress=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Music(bot))
