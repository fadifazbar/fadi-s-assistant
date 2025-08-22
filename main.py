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

        # Load cogs (same as before)
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.serverinfo")
        await self.load_extension("cogs.reactionrole")
        await self.load_extension("cogs.snipeeditsnipe")
        await self.load_extension("cogs.music")
        await self.load_extension("cogs.url_download")

        # 🔄 Auto-sync slash commands globally
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} commands globally")
        except Exception as e:
            logger.error(f"❌ Failed to sync commands: {e}")

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

    async def on_command_error(self, ctx, error):
        """Global error handler for prefix commands"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided!")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds."
            )
        else:
            logger.error(f"⚠️ Unhandled command error: {error}")
            await ctx.send("❌ An error occurred while processing the command.")

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
    # Load extra cogs (same as your original)
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
