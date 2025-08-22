import discord
from discord.ext import commands
import logging
from config import Config
from utils.logging_config import setup_logging

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

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"🤖 Bot is ready! Logged in as {self.user}")
        logger.info(f"🆔 Bot ID: {self.user.id}")
        logger.info(f"💥 Serving {len(self.guilds)} guilds")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"🤩 Use {Config.PREFIX}help | Moderation And Fun Bot :p"
            ),
            status=discord.Status.online
        )

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"❌ Failed to sync commands: {e}")
        

    async def on_command_error(self, ctx, error):
        """Global error handler for prefix commands"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided!")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds."
            )
        else:
            logger.error(f"Unhandled command error: {error}")
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
            logger.error(f"Unhandled slash command error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing the command.",
                    ephemeral=True
                )

    async def on_guild_join(self, guild):
        """Called when bot joins a guild"""
        logger.info(f"✅ Joined guild: {guild.name} ({guild.id})")

    async def on_guild_remove(self, guild):
        """Called when bot leaves a guild"""
        logger.info(f"❌ Left guild: {guild.name} ({guild.id})")


async def main():
    """Main function to run the bot"""
    bot = ModBot()

    # Load core cogs
    await bot.load_extension("cogs.moderation")
    await bot.load_extension("cogs.general")
    await bot.load_extension("cogs.serverinfo")
    await bot.load_extension("cogs.reactionrole")
    await bot.load_extension("cogs.snipeeditsnipe")
    await bot.load_extension("cogs.music")
    await bot.load_extension("cogs.url_download")

    # Load extra cogs
    await bot.load_extension("messagelogger")
    await bot.load_extension("invite")
    await bot.load_extension("xoxo")

    # Start bot
    await bot.start(Config.BOT_TOKEN)

# ⚠️ Do not auto-run here — server.py controls it
if __name__ == "__main__":
    import warnings
    warnings.warn("Run server.py instead of main.py")
