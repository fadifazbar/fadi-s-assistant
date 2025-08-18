import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os

CONFIG_FILE = "log_channels.json"

class MessageLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channels = self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.log_channels, f, indent=4)

    # Command for admins to set the log channel
    @app_commands.command(name="saylogs", description="Select a channel to log all say command usage")
    @app_commands.checks.has_permissions(administrator=True)
    async def viewmessage(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.log_channels[str(interaction.guild.id)] = channel.id
        self.save_config()
        await interaction.response.send_message(
            f"✅ Say command logs will now be sent to {channel.mention}",
            ephemeral=True
        )

    # Internal helper to log messages
    async def log_say(self, author: discord.Member, message: str, channel: discord.TextChannel):
        guild_id = str(channel.guild.id)
        if guild_id not in self.log_channels:
            return  # no log channel set for this guild

        log_channel = channel.guild.get_channel(self.log_channels[guild_id])
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
        embed.set_thumbnail(url=author.display_avatar.url)

        await log_channel.send(embed=embed)

    # Hook into prefix say command
    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        if ctx.command and ctx.command.name == "say":
            await self.log_say(ctx.author, ctx.message.content[len(ctx.prefix + ctx.command.name):].strip(), ctx.channel)

    # Hook into slash say command
    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        if command.name == "say":
            message = interaction.namespace.message
            await self.log_say(interaction.user, message, interaction.channel)


async def setup(bot):
    await bot.add_cog(MessageLogger(bot))
