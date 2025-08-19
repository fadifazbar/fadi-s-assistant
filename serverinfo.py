import discord
from discord.ext import commands
from discord import app_commands
from typing import Union

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------
    # Server Info - Prefix
    # -------------------
    @commands.command(name="serverinfo")
    async def serverinfo_prefix(self, ctx):
        await self.send_server_info(ctx.guild, ctx, is_interaction=False)

    # -------------------
    # Server Info - Slash
    # -------------------
    @app_commands.command(name="serverinfo", description="Shows info about the server")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        await self.send_server_info(interaction.guild, interaction, is_interaction=True)

    # -------------------
    # Helper function
    # -------------------
    async def send_server_info(self, guild: discord.Guild, target: Union[commands.Context, discord.Interaction], is_interaction: bool):
        # Count humans and bots
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        total_members = len(guild.members)

        # Channels & roles
        total_channels = len(guild.channels)
        total_roles = len(guild.roles)

        # Verification level with emojis
        verif_levels = {
            discord.VerificationLevel.none: "None 🔓",
            discord.VerificationLevel.low: "Low 🔒",
            discord.VerificationLevel.medium: "Medium 🛡️",
            discord.VerificationLevel.high: "High ⚔️",
            discord.VerificationLevel.extreme: "Highest 🏰"
        }
        verif = verif_levels.get(guild.verification_level, "Unknown ❓")

        # Emojis
        static_emojis = len([e for e in guild.emojis if not e.animated])
        animated_emojis = len([e for e in guild.emojis if e.animated])

        # Boost info
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count

        # Random embed color
        embed_color = discord.Color.random()

        # Create embed
        embed = discord.Embed(
            title=guild.name,
            color=embed_color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Server ID: {guild.id}")
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)

        # Fields
        embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="🧑 Members", value=f"Humans: {humans}\nBots: {bots}\nTotal: {total_members}", inline=True)
        embed.add_field(name="🛠 Channels & Roles", value=f"Channels: {total_channels}\nRoles: {total_roles}", inline=True)
        embed.add_field(name="🔒 Verification", value=verif, inline=True)
        embed.add_field(name="🚀 Boosts", value=f"Level: {boost_level}\nBoosters: {boost_count}", inline=True)
        embed.add_field(name="😊 Emojis", value=f"Static: {static_emojis}\nAnimated: {animated_emojis}", inline=True)

        # Send response
        if is_interaction:
            await target.response.send_message(embed=embed)
        else:
            await target.send(embed=embed)

# -------------------
# Setup function
# -------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
