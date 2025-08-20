import asyncio
import datetime

import discord
from discord.ext import commands, tasks
from discord import app_commands

import yt_dlp

--- YTDL OPTIONS (fix SABR issue mid-2025) ---

ytdl_format_options = { "format": "bestaudio[ext=webm][acodec=opus]/bestaudio/best", "noplaylist": True, "quiet": True, "extract_flat": False, "default_search": "ytsearch", "source_address": "0.0.0.0",  # Force IPv4 }

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

ffmpeg_options = { "options": "-vn" }

class YTDLSource(discord.PCMVolumeTransformer): def init(self, source, *, data, requester): super().init(source) self.data = data self.requester = requester

@classmethod
async def create_source(cls, query, *, loop, requester):
    loop = loop or asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))

    if "entries" in data:
        data = data["entries"][0]

    filename = data["url"]
    return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, requester=requester)

class MusicPlayer: def init(self, ctx): self.ctx = ctx self.queue = [] self.current = None self.looping = False self.idle_task = None

def add_to_queue(self, source):
    self.queue.append(source)
    return source

async def play_next(self):
    if self.looping and self.current:
        self.queue.insert(0, self.current)

    if self.queue:
        self.current = self.queue.pop(0)
        self.ctx.voice_client.play(
            self.current,
            after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(), self.ctx.bot.loop)
        )
        await self.announce_now_playing()
    else:
        self.current = None
        self.start_idle_timer()

def start_idle_timer(self):
    if self.idle_task:
        self.idle_task.cancel()

    async def idle_disconnect():
        await asyncio.sleep(300)  # 5 min
        if not self.current and self.ctx.voice_client:
            await self.ctx.voice_client.disconnect()
            embed = discord.Embed(
                title="⏹ Disconnected",
                description="No music for 5 minutes. Leaving voice channel.",
                color=discord.Color.red()
            )
            await self.ctx.send(embed=embed)

    self.idle_task = self.ctx.bot.loop.create_task(idle_disconnect())

async def announce_now_playing(self):
    if not self.current:
        return
    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"[{self.current.data['title']}]({self.current.data['webpage_url']})",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=self.current.data.get("thumbnail"))
    embed.add_field(name="Duration", value=str(datetime.timedelta(seconds=self.current.data.get("duration", 0))), inline=True)
    embed.add_field(name="Requested by", value=self.current.requester.mention, inline=True)
    await self.ctx.send(embed=embed)

class Music(commands.Cog): def init(self, bot): self.bot = bot self.players = {}

def get_player(self, ctx):
    return self.players.setdefault(ctx.guild.id, MusicPlayer(ctx))

async def join_vc(self, interaction):
    channel = interaction.user.voice.channel
    if not interaction.guild.voice_client:
        await channel.connect()

# --- Commands ---
@app_commands.command(name="play", description="Play a song from YouTube or search")
async def play(self, interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    player = self.get_player(ctx)

    if not ctx.voice_client:
        await self.join_vc(interaction)

    source = await YTDLSource.create_source(query, loop=self.bot.loop, requester=interaction.user)
    player.add_to_queue(source)

    if not ctx.voice_client.is_playing():
        await player.play_next()
    else:
        embed = discord.Embed(
            title="➕ Added to Queue",
            description=f"[{source.data['title']}]({source.data['webpage_url']})",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=source.data.get("thumbnail"))
        embed.add_field(name="Duration", value=str(datetime.timedelta(seconds=source.data.get("duration", 0))), inline=True)
        embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
        await interaction.followup.send(embed=embed)

@app_commands.command(name="skip", description="Skip the current song")
async def skip(self, interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await interaction.followup.send("⏭ Skipped!")
    else:
        await interaction.followup.send("❌ Nothing is playing.")

@app_commands.command(name="queue", description="Show the current queue")
async def queue(self, interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    player = self.get_player(ctx)
    if not player.queue:
        return await interaction.followup.send("📭 The queue is empty.")

    embed = discord.Embed(title="🎵 Queue", color=discord.Color.purple())
    for i, track in enumerate(player.queue[:10], 1):
        embed.add_field(
            name=f"{i}. {track.data['title']}",
            value=f"Requested by {track.requester.mention}",
            inline=False
        )
    await interaction.followup.send(embed=embed)

@app_commands.command(name="loop", description="Toggle loop for current track")
async def loop(self, interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    player = self.get_player(ctx)
    player.looping = not player.looping
    await interaction.followup.send("🔁 Looping enabled" if player.looping else "▶ Looping disabled")

@app_commands.command(name="stop", description="Stop music and clear queue")
async def stop(self, interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    player = self.get_player(ctx)
    player.queue.clear()
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    await interaction.followup.send("⏹ Stopped and cleared queue.")

@app_commands.command(name="nowplaying", description="Show what is currently playing")
async def nowplaying(self, interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    player = self.get_player(ctx)
    if not player.current:
        return await interaction.followup.send("❌ Nothing is currently playing.")

    pos = int(ctx.voice_client.source.read()) if ctx.voice_client and ctx.voice_client.source else 0
    total = player.current.data.get("duration", 0)
    bar_length = 20
    filled = int((pos / total) * bar_length) if total > 0 else 0
    progress_bar = "▬" * filled + "🔘" + "▬" * (bar_length - filled)

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"[{player.current.data['title']}]({player.current.data['webpage_url']})\n{progress_bar}",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=player.current.data.get("thumbnail"))
    embed.add_field(name="Duration", value=str(datetime.timedelta(seconds=total)), inline=True)
    embed.add_field(name="Requested by", value=player.current.requester.mention, inline=True)
    await interaction.followup.send(embed=embed)

async def setup(bot): await bot.add_cog(Music(bot))

