import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import sqlite3
import os

# Use Railway's persistent volume (make sure you mounted /data in Railway)
DB_FILE = "/data/log_channels.db"

class MessageLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # allow multiple threads (discord.py runs async)
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        """Create the table if it doesn't exist"""
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS log_channels (
                guild_id TEXT PRIMARY KEY,
                channel_id INTEGER
            )"""
        )
        self.conn.commit()

    def set_log_channel(self, guild_id: str, channel_id: int):
        """Insert or update a guild's log channel"""
        self.cursor.execute(
            "INSERT OR REPLACE INTO log_channels (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        self.conn.commit()

    def get_log_channel(self, guild_id: str):
        """Fetch the log channel for a guild"""
        self.cursor.execute("SELECT channel_id FROM log_channels WHERE guild_id = ?", (guild_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    # Admin command to set the log channel
    @app_commands.command(name="saylogs", description="Select a channel to log all say command usage")
    @app_commands.checks.has_permissions(administrator=True)
    async def viewmessage(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.set_log_channel(str(interaction.guild.id), channel.id)
        await interaction.response.send_message(
            f"✅ Say command logs will now be sent to {channel.mention}",
            ephemeral=True
        )

    # OPTIONAL: Check which log channel is currently set
    @app_commands.command(name="checklogs", description="Check which channel is set for say command logs")
    @app_commands.checks.has_permissions(administrator=True)
    async def check_logs(self, interaction: discord.Interaction):
        log_channel_id = self.get_log_channel(str(interaction.guild.id))
        if log_channel_id:
            channel = interaction.guild.get_channel(log_channel_id)
            await interaction.response.send_message(
                f"📍 Current log channel: {channel.mention if channel else '⚠️ Not found'}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("⚠️ No log channel set.", ephemeral=True)

    # Internal helper
    async def log_say(self, author: discord.Member, message: str, channel: discord.TextChannel, bot_message: discord.Message = None):
        guild_id = str(channel.guild.id)
        log_channel_id = self.get_log_channel(guild_id)
        if not log_channel_id:
            return

        log_channel = channel.guild.get_channel(log_channel_id)
        if log_channel is None:
            return

        embed = discord.Embed(
            title="💬 Say Command Used",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="👤 User", value=author.mention, inline=True)
        embed.add_field(name="📅 Date", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
        embed.add_field(name="💬 Message", value=message, inline=False)
        embed.add_field(name="📍 Channel", value=channel.mention, inline=True)

        if bot_message:
            embed.add_field(name="🔗 Message Link", value=f"[Jump to Message]({bot_message.jump_url})", inline=False)

        embed.set_thumbnail(url=author.display_avatar.url)
        await log_channel.send(embed=embed)

    # Hook into prefix "say" command
    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        if ctx.command and ctx.command.name == "say":
            bot_message = None
            try:
                async for msg in ctx.channel.history(limit=5):
                    if msg.author == self.bot.user:
                        bot_message = msg
                        break
            except:
                pass

            await self.log_say(
                ctx.author,
                ctx.message.content[len(ctx.prefix + ctx.command.name):].strip(),
                ctx.channel,
                bot_message
            )

    # Hook into slash "say" command
    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        if command.name == "say":
            message = interaction.namespace.message
            bot_message = None
            try:
                async for msg in interaction.channel.history(limit=5):
                    if msg.author == self.bot.user:
                        bot_message = msg
                        break
            except:
                pass

            await self.log_say(interaction.user, message, interaction.channel, bot_message)


async def setup(bot):
    await bot.add_cog(MessageLogger(bot))
