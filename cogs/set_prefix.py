# cogs/prefix.py
from discord.ext import commands
from discord import app_commands, Interaction
from config import Config
import discord
import datetime
import json

LOG_FILE = "/data/prefix_logs.json"

def log_prefix_change(guild_id, user, old_prefix, new_prefix):
    """Store prefix change in JSON file."""
    data = {}
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        pass  # File will be created

    if str(guild_id) not in data:
        data[str(guild_id)] = []

    data[str(guild_id)].append({
        "time": datetime.datetime.utcnow().isoformat(),
        "user": f"{user} ({user.id})",
        "old_prefix": old_prefix,
        "new_prefix": new_prefix
    })

    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)

class Prefix(commands.Cog):
    """Manage server prefixes for both prefix and slash commands"""

    def __init__(self, bot):
        self.bot = bot

    # -----------------------------
    # Prefix command
    # -----------------------------
@commands.command(name="setprefix")
@commands.has_permissions(administrator=True)
async def setprefix_prefix(self, ctx, new_prefix):
    old_prefix = Config.get_prefix(ctx.guild.id)
    Config.set_prefix(ctx.guild.id, new_prefix)
    await ctx.send(f"✅ Prefix changed from `{old_prefix}` to `{new_prefix}`.")

    # Update bot presence immediately
    await self.bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"🤩 Use {new_prefix}help | {ctx.guild.name}"
        ),
        status=discord.Status.online
    )

    # Logging
    log_prefix_change(ctx.guild.id, ctx.author, old_prefix, new_prefix)
    log_channel = discord.utils.get(ctx.guild.text_channels, name="prefix-logs")
    if log_channel:
        embed = discord.Embed(
            title="Prefix Changed",
            color=Config.COLORS["info"],
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{ctx.author} ({ctx.author.id})", inline=False)
        embed.add_field(name="Old Prefix", value=old_prefix, inline=True)
        embed.add_field(name="New Prefix", value=new_prefix, inline=True)
        await log_channel.send(embed=embed)

    # -----------------------------
    # Slash command
    # -----------------------------
@app_commands.command(name="setprefix", description="Change the server prefix")
@app_commands.default_permissions(administrator=True)
async def setprefix_slash(self, interaction: discord.Interaction, new_prefix: str):
    old_prefix = Config.get_prefix(interaction.guild.id)
    Config.set_prefix(interaction.guild.id, new_prefix)
    await interaction.response.send_message(f"✅ Prefix changed from `{old_prefix}` to `{new_prefix}`.")

    # Update bot presence immediately
    await self.bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"🤩 Use {new_prefix}help | {interaction.guild.name}"
        ),
        status=discord.Status.online
    )

    # Logging
    log_prefix_change(interaction.guild.id, interaction.user, old_prefix, new_prefix)
    log_channel = discord.utils.get(interaction.guild.text_channels, name="prefix-logs")
    if log_channel:
        embed = discord.Embed(
            title="Prefix Changed",
            color=Config.COLORS["info"],
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{interaction.user} ({interaction.user.id})", inline=False)
        embed.add_field(name="Old Prefix", value=old_prefix, inline=True)
        embed.add_field(name="New Prefix", value=new_prefix, inline=True)
        await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Prefix(bot))
