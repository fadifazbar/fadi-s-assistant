import discord
from discord.ext import commands
import asyncio
import logging
from config import Config
from utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


class ModBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        intents.moderation = True
        intents.presences = True

        super().__init__(
            command_prefix=Config.PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True
        )

    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info("Setting up bot...")

        # Load cogs
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.serverinfo")
        await self.load_extension("cogs.reactionrole")
        await self.load_extension("cogs.snipeeditsnipe")
        await self.load_extension("cogs.music")
        await self.load_extension("cogs.url_download")  # this one no longer uses server.py

        logger.info("✅ Loaded cogs (skipping slash command sync)")

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"✅ Bot is ready! Logged in as {self.user}")
        logger.info(f"🆔 Bot ID: {self.user.id}")
        logger.info(f"📊 Serving {len(self.guilds)} guilds")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"🤩 Use {Config.PREFIX}help | Moderation And Fun Bot :p"
            ),
            status=discord.Status.online
        )

    # ----------------------------
    # SYNC COMMAND (owner only)
    # ----------------------------
    @commands.command(name="sync", help="Sync slash commands. Usage: !sync [here|all|clear]")
    @commands.is_owner()
    async def sync_prefix(self, ctx: commands.Context, scope: str = None):
        try:
            if scope is None:
                return await ctx.send("❌ Usage: `!sync here` (this server), `!sync all` (global), or `!sync clear` (remove guild overrides).")

            scope = scope.lower()

            if scope == "here":
                if ctx.guild is None:
                    return await ctx.send("❌ This must be used in a server.")
                # Copy global commands into THIS guild, then sync for instant availability
                self.tree.copy_global_to(guild=ctx.guild)
                synced = await self.tree.sync(guild=ctx.guild)
                msg = f"✅ Synced **{len(synced)}** commands to **{ctx.guild.name}** ({ctx.guild.id})."

            elif scope == "all":
                # Clear local cache of global cmds (avoids dupes), then sync globally
                self.tree.clear_commands(guild=None)
                synced = await self.tree.sync()
                msg = f"🌍 Globally synced **{len(synced)}** commands to all guilds."

            elif scope == "clear":
                if ctx.guild is None:
                    return await ctx.send("❌ This must be used in a server.")
                # Remove per-guild overrides, effectively leaving only global set
                self.tree.clear_commands(guild=ctx.guild)
                await self.tree.sync(guild=ctx.guild)
                msg = f"🧹 Cleared per-guild commands for **{ctx.guild.name}** ({ctx.guild.id})."

            else:
                return await ctx.send("❌ Usage: `!sync here`, `!sync all`, or `!sync clear`.")

            # Send in channel
            await ctx.send(msg)
            # DM the invoker (owner)
            try:
                await ctx.author.send(msg)
            except discord.Forbidden:
                await ctx.send("⚠️ Could not DM you the result.")
            # Log it
            logger.info(msg)

        except Exception as e:
            error_msg = f"❌ Sync failed: {e}"
            await ctx.send(error_msg)
            try:
                await ctx.author.send(error_msg)
            except discord.Forbidden:
                pass
            logger.exception("Sync failed")


    async def on_app_command_error(self, interaction, error):
        """Global error handler for slash commands"""
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command!",
                ephemeral=True
            )
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
        else:
            logger.error(f"⚠️ Unhandled slash command error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing the command.",
                    ephemeral=True
                )

    async def on_guild_join(self, guild):
        logger.info(f"📥 Joined guild: {guild.name} ({guild.id})")

    async def on_guild_remove(self, guild):
        logger.info(f"📤 Left guild: {guild.name} ({guild.id})")


# ----------------------------
# Run the bot
# ----------------------------
bot = ModBot()

async def main():
    """Main function to run the bot"""
    # Load extra cogs
    await bot.load_extension("messagelogger")
    await bot.load_extension("invite")
    await bot.load_extension("xoxo")

    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN is not set in config!")
        return

    try:
        await bot.start(Config.BOT_TOKEN)
    except discord.LoginFailure:
        logger.error("❌ Invalid bot token provided!")
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
