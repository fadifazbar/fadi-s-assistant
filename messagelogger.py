import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os

# Use Railway's persistent volume (make sure you mounted /data in Railway)
CONFIG_FILE = "/data/log_channels.json"

class MessageLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channels = self.load_config()
        print("[DEBUG] Cog initialized. Loaded log_channels:", self.log_channels)

    def load_config(self):
        """Load log channel configuration from JSON"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    print(f"[DEBUG] Loaded config from {CONFIG_FILE}: {data}")
                    return data
            except json.JSONDecodeError as e:
                print("[ERROR] JSON decode error:", e)
                return {}
        else:
            print(f"[DEBUG] No config file found at {CONFIG_FILE}. Starting fresh.")
        return {}

    def save_config(self):
        """Save log channel configuration to JSON"""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.log_channels, f, indent=4)
            print(f"[DEBUG] Saved config to {CONFIG_FILE}: {self.log_channels}")
        except Exception as e:
            print("[ERROR] Failed to save config:", e)

    def set_log_channel(self, guild_id: str, channel_id: int):
        """Insert or update a guild's log channel"""
        print(f"[DEBUG] Setting log channel for guild {guild_id} -> {channel_id}")
        self.log_channels[guild_id] = channel_id
        self.save_config()

    def get_log_channel(self, guild_id: str):
        """Fetch the log channel for a guild"""
        channel_id = self.log_channels.get(guild_id)
        print(f"[DEBUG] Fetch log channel for guild {guild_id}: {channel_id}")
        return channel_id

    # Admin command to set the log channel
    @app_commands.command(name="saylogs", description="Select a channel to log all say command usage")
    @app_commands.checks.has_permissions(administrator=True)
    async def viewmessage(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.set_log_channel(str(interaction.guild.id), channel.id)
        await interaction.response.send_message(
            f"✅ Say command logs will now be sent to {channel.mention}",
            ephemeral=True
        )
        print(f"[DEBUG] /saylogs called in guild {interaction.guild.id}, set to {channel.id}")

    # OPTIONAL: Check which log channel is currently set
    @app_commands.command(name="saychecklogs", description="Check which channel is set for say command logs")
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
        print(f"[DEBUG] /checklogs called in guild {interaction.guild.id}, result: {log_channel_id}")

    # Internal helper
    async def log_say(self, author: discord.Member, message: str, channel: discord.TextChannel, bot_message: discord.Message = None):
        guild_id = str(channel.guild.id)
        log_channel_id = self.get_log_channel(guild_id)
        if not log_channel_id:
            print(f"[DEBUG] No log channel set for guild {guild_id}, skipping log_say.")
            return

        log_channel = channel.guild.get_channel(log_channel_id)
        if log_channel is None:
            print(f"[DEBUG] Config has {log_channel_id} but channel not found in guild {guild_id}.")
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
        print(f"[DEBUG] Logged say command from {author} in guild {guild_id} to channel {log_channel_id}")

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
            except Exception as e:
                print("[ERROR] Failed fetching bot message in on_command_completion:", e)

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
            except Exception as e:
                print("[ERROR] Failed fetching bot message in on_app_command_completion:", e)

            await self.log_say(interaction.user, message, interaction.channel, bot_message)

async def setup(bot):
    await bot.add_cog(MessageLogger(bot))

