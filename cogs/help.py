import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

# Try importing Config, fallback if missing
try:
    from config import Config
    PREFIX = Config.PREFIX
    COLORS = Config.COLORS
except ImportError:
    PREFIX = "$"
    COLORS = {"info": discord.Color.blue()}


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Add cog names here to block them from showing in help
        self.blocked_cogs = {"WipeAndRebuild"}  

    # --- Help command (Prefix) ---
    @commands.command(name="help", aliases=["cmds", "cmnds", "command", "commands"])
    async def help_prefix(self, ctx):
        await self._show_help(ctx)

    # --- Help command (Slash) ---
    @app_commands.command(name="help", description="Show help information")
    async def help_slash(self, interaction: discord.Interaction):
        await self._show_help(interaction)

    # --- Internal helper ---
    async def _show_help(self, ctx_or_interaction):
        embed = discord.Embed(
            title="🤖 Bot Help",
            color=COLORS.get("info", discord.Color.blue()),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Prefix: {PREFIX} | Slash commands also available")

        embed.description = (
            f"A powerful bot with both prefix (`{PREFIX}`) and slash (`/`) commands.\n"
            f"Use `{PREFIX}help` to see this menu."
        )

        blocked_list = []

        # Loop through cogs and add their commands
        for cog_name, cog in self.bot.cogs.items():
            if cog_name in self.blocked_cogs:
                blocked_list.append(cog_name)
                continue  # skip blocked cogs

            cmds = [
                f"`{PREFIX}{c.name}`"
                for c in cog.get_commands()
                if not c.hidden
            ]
            if cmds:
                embed.add_field(
                    name=f"{cog_name} Commands",
                    value=", ".join(cmds),
                    inline=False
                )

        # Send safely
        await self._send_response(
            ctx_or_interaction,
            embed=embed,
            ephemeral=isinstance(ctx_or_interaction, discord.Interaction)
        )

    # --- Safe send helper ---
    async def _send_response(self, ctx_or_interaction, embed: discord.Embed = None, ephemeral: bool = False):
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(embed=embed)
        elif isinstance(ctx_or_interaction, discord.Interaction):
            if not ctx_or_interaction.response.is_done():
                await ctx_or_interaction.response.send_message(embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
    
