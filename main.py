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
        logger.info(f"✅ Bot ready! Logged in as {self.user}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"Use {Config.PREFIX}help | Moderation and Fun Bot :p"
            ),
            status=discord.Status.online
        )

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
