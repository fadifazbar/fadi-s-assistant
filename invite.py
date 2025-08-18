import discord
from discord.ext import commands
from discord import app_commands

INVITE_LINK = "https://discord.com/oauth2/authorize?client_id=1406641375641993317&permissions=8&integration_type=0&scope=bot"

class Invite(commands.Cog):
    """Invite command (prefix + slash)"""

    def __init__(self, bot):
        self.bot = bot

    # Prefix command
    @commands.command(name="invite")
    async def invite_prefix(self, ctx: commands.Context):
        """Get the bot's invite link"""
        try:
            await ctx.author.send(f"🔗 **Invite me to your server:**\n{INVITE_LINK}")
            await ctx.reply("✅ I sent you the invite link in DMs!", mention_author=False)
        except discord.Forbidden:
            await ctx.reply(f"🔗 **Invite me to your server:**\n{INVITE_LINK}", mention_author=False)

    # Slash command
    @app_commands.command(name="invite", description="Get the bot's invite link")
    async def invite_slash(self, interaction: discord.Interaction):
        """Get the bot's invite link (ephemeral)"""
        await interaction.response.send_message(
            f"🔗 **Invite me to your server:**\n{INVITE_LINK}",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Invite(bot))
