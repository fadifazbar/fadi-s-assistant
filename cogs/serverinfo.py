import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Union

class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------
    # Prefix command
    # ------------------------
    @commands.command(name="serverinfo")
    async def serverinfo_prefix(self, ctx):
        await self.send_server_info(ctx.guild, ctx, is_interaction=False)

    # ------------------------
    # Slash command
    # ------------------------
    @app_commands.command(name="serverinfo", description="Show information about this server")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        await self.send_server_info(interaction.guild, interaction, is_interaction=True)

    # ------------------------
    # Core function
    # ------------------------
    async def send_server_info(self, guild: discord.Guild, ctx_or_interaction: Union[commands.Context, discord.Interaction], is_interaction: bool):
        # Count members
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        total_members = guild.member_count

        # Count channels & roles
        total_channels = len(guild.channels)
        total_roles = len(guild.roles)

        # Verification level mapping
verification_levels = {
    discord.VerificationLevel.none: "None 🔓",
    discord.VerificationLevel.low: "Low 🔒",
    discord.VerificationLevel.medium: "Medium 🛡️",
    discord.VerificationLevel.high: "High 🔐"
}
verif = verification_levels.get(guild.verification_level, "Unknown ❔")

        # Server boosts
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count

        # Emojis
        static_emojis = len([e for e in guild.emojis if not e.animated])
        animated_emojis = len([e for e in guild.emojis if e.animated])

        # Random embed color
        embed_color = discord.Color.random()

        # Create embed
        embed = discord.Embed(
            title=guild.name,
            color=embed_color
        )
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)

        # Fields
        embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="🧑 Members", value=f"Humans: {humans}\nBots: {bots}\nTotal: {total_members}", inline=True)
        embed.add_field(name="🛠 Channels & Roles", value=f"Channels: {total_channels}\nRoles: {total_roles}", inline=True)
        embed.add_field(name="🔒 Verification", value=verif, inline=True)
        embed.add_field(name="🚀 Boosts", value=f"Level: {boost_level}\nBoosters: {boost_count}", inline=True)
        embed.add_field(name="😊 Emojis", value=f"Static: {static_emojis}\nAnimated: {animated_emojis}", inline=True)

        # Send the embed
        if is_interaction:
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)


# ------------------------
# Cog setup
# ------------------------
async def setup(bot):
    await bot.add_cog(ServerInfo(bot))
