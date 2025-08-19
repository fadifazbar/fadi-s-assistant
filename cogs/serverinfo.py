import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional

class ServerInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------
    # Prefix command
    # -------------------
    @commands.command(name="serverinfo")
    async def serverinfo_prefix(self, ctx):
        await self.send_server_info(ctx.guild, ctx, is_interaction=False)

    # -------------------
    # Slash command
    # -------------------
    @app_commands.command(name="serverinfo", description="Shows server info")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        await self.send_server_info(interaction.guild, interaction, is_interaction=True)

    # -------------------
    # Helper function
    # -------------------
    async def send_server_info(self, guild: discord.Guild, ctx_or_interaction, is_interaction: bool):
        # Random embed color
        color = discord.Color(random.randint(0, 0xFFFFFF))
        embed = discord.Embed(
            title=f"📝 {guild.name}",
            description=f"**# {guild.name}**",
            color=color
        )
        
        # Server icon
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Members
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        total_members = guild.member_count

        # Roles & Channels
        total_roles = len(guild.roles)
        total_channels = len(guild.channels)

        # Stickers
        total_stickers = len(guild.stickers)

        # Boosts
        boost_count = guild.premium_subscription_count
        boost_level = guild.premium_tier

        # Verification level with emoji
        verif_levels = {
            discord.VerificationLevel.none: "None ❌",
            discord.VerificationLevel.low: "Low ⚠️",
            discord.VerificationLevel.medium: "Medium 🛡️",
            discord.VerificationLevel.high: "High 🔒",
            discord.VerificationLevel.highest: "Highest 🏰"
        }
        verif = verif_levels.get(guild.verification_level, "Unknown ❓")

        # Emojis
        static_emojis_list = [str(e) for e in guild.emojis if not e.animated]
        animated_emojis_list = [str(e) for e in guild.emojis if e.animated]
        static_emojis = f"{len(static_emojis_list)}\n{' '.join(static_emojis_list)}" if static_emojis_list else "0"
        animated_emojis = f"{len(animated_emojis_list)}\n{' '.join(animated_emojis_list)}" if animated_emojis_list else "0"

        # Add fields with emojis
        embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="🧑 Members", value=f"Humans: {humans}\nBots: {bots}\nTotal: {total_members}", inline=True)
        embed.add_field(name="🛠 Channels & Roles", value=f"Channels: {total_channels}\nRoles: {total_roles}", inline=True)
        embed.add_field(name="🔒 Verification", value=verif, inline=True)
        embed.add_field(name="🚀 Boosts", value=f"Level: {boost_level}\nBoosters: {boost_count}", inline=True)
        embed.add_field(name="😊 Static Emojis", value=static_emojis, inline=False)
        embed.add_field(name="✨ Animated Emojis", value=animated_emojis, inline=False)
        embed.add_field(name="📌 Stickers", value=f"Total: {total_stickers}", inline=True)
        embed.add_field(name="📅 Created On", value=guild.created_at.strftime("%d %B %Y"), inline=True)

        # Send the embed
        if is_interaction:
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

# Setup function for the cog
async def setup(bot: commands.Bot):
    await bot.add_cog(ServerInfo(bot))
