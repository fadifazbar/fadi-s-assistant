import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional

class ServerInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="serverinfo")
    async def serverinfo_prefix(self, ctx: commands.Context):
        await self.send_server_info(ctx.guild, ctx, is_interaction=False)

    @app_commands.command(name="serverinfo", description="Shows information about the server")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        await self.send_server_info(interaction.guild, interaction, is_interaction=True)

    async def send_server_info(self, guild: discord.Guild, ctx_or_interaction, is_interaction=False):
        # Random embed color
        color = discord.Color.random()

        # Owner
        owner = guild.owner.mention if guild.owner else "Unknown"

        # Members
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        total_members = humans + bots

        # Channels & Roles
        total_channels = len(guild.channels)
        total_roles = len(guild.roles)

        # Verification level with emojis
        verif_dict = {
            discord.VerificationLevel.none: "🟢 None",
            discord.VerificationLevel.low: "🟡 Low",
            discord.VerificationLevel.medium: "🛑 Medium",
            discord.VerificationLevel.high: "⛔ High",
            discord.VerificationLevel.highest: "📛 Highest",
        }
        verif = verif_dict.get(guild.verification_level, "Unknown ❔")

        # Boosts
        boost_level = guild.premium_tier.value if hasattr(guild.premium_tier, "value") else guild.premium_tier
        boost_count = guild.premium_subscription_count

        # Stickers count
        sticker_count = len(guild.stickers)

        # Emojis
        static_emojis_list = [str(e) for e in guild.emojis if not e.animated]
        animated_emojis_list = [str(e) for e in guild.emojis if e.animated]

        def truncate_list(items, limit=1000):
            joined = " ".join(items)
            if len(joined) > limit:
                cut_length = limit - 15
                truncated = joined[:cut_length].rstrip()
                return f"{truncated} … +{len(items) - len(truncated.split())} more"
            return joined

        static_emojis = f"{len(static_emojis_list)}\n{truncate_list(static_emojis_list)}" if static_emojis_list else "0"
        animated_emojis = f"{len(animated_emojis_list)}\n{truncate_list(animated_emojis_list)}" if animated_emojis_list else "0"

        # Create embed
        embed = discord.Embed(
            title=f"Server Info",
            description=f"# {guild.name}",
            color=color
        )

        # Server icon on top right
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Add fields with emojis
        embed.add_field(name="👑 Owner", value=owner, inline=True)
        embed.add_field(name="🧑 Members", value=f"🤩 Humans: {humans}\n🤖 Bots: {bots}\n💗 Total: {total_members}", inline=True)
        embed.add_field(name="🛠 Channels & Roles", value=f"💬 Channels: {total_channels}\n✨ Roles: {total_roles}", inline=True)
        embed.add_field(name="🔒 Verification", value=verif, inline=True)
        embed.add_field(name="🚀 Boosts", value=f"🔮 Level: {boost_level}\n🚀 Boosts: {boost_count}", inline=True)
        embed.add_field(name="📦 Stickers", value=f"🥶 Total: {sticker_count}", inline=True)
        embed.add_field(name="😊 Static Emojis", value=static_emojis, inline=False)
        embed.add_field(name="🎉 Animated Emojis", value=animated_emojis, inline=False)
        embed.add_field(name="🕒 Created At", value=guild.created_at.strftime("%d %b %Y %H:%M"), inline=True)

        # Send embed
        if is_interaction:
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerInfo(bot))
