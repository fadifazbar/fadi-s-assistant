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

    # --- Help command (Prefix) ---
    @commands.command(name="help", aliases=["cmds", "cmnds", "command", "commands"])
    async def help_prefix(self, ctx, command_name: str = None):
        await self._show_help(ctx, command_name)

    # --- Help command (Slash) ---
    @app_commands.command(name="help", description="Show help information")
    @app_commands.describe(command="Specific command to get help for")
    async def help_slash(self, interaction: discord.Interaction, command: str = None):
        await self._show_help(interaction, command)

    # --- Internal helper ---
    async def _show_help(self, ctx_or_interaction, command_name: str = None):
        embed = discord.Embed(
            title="🤖 Bot Help",
            color=COLORS.get("info", discord.Color.blue()),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Prefix: {PREFIX} | Slash commands also available")

        if command_name:
            # Show detailed help for a specific command
            cmd = self.bot.get_command(command_name)
            if cmd:
                usage = f"{PREFIX}{cmd.qualified_name} {cmd.signature}".strip()
                embed.add_field(
                    name=f"📌 {cmd.qualified_name}",
                    value=f"**Usage:** `{usage}`\n{cmd.help or 'No description provided.'}",
                    inline=False
                )
            else:
                embed.description = f"❌ Command `{command_name}` not found."
        else:
            # Show all commands grouped by cog
            embed.description = (
                f"A powerful bot with both prefix (`{PREFIX}`) and slash (`/`) commands.\n"
                f"Use `{PREFIX}help <command>` for detailed help."
            )

            for cog_name, cog in self.bot.cogs.items():
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
        await self._send_response(ctx_or_interaction, embed=embed, ephemeral=isinstance(ctx_or_interaction, discord.Interaction))

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
                                                        
