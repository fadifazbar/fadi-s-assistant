import discord
from discord.ext import commands
import asyncio
import logging
import os
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
        await self.load_extension('cogs.moderation')
        await self.load_extension('cogs.general')
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Serving {len(self.guilds)} guilds")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{Config.PREFIX}help | Moderation And Fun Bot"
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
            await ctx.send(f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds.")
        else:
            logger.error(f"Unhandled command error: {error}")
            await ctx.send("❌ An error occurred while processing the command.")
    
    async def on_app_command_error(self, interaction, error):
        """Global error handler for slash commands"""
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds.", ephemeral=True)
        else:
            logger.error(f"Unhandled slash command error: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while processing the command.", ephemeral=True)
    
    async def on_guild_join(self, guild):
        """Called when bot joins a guild"""
        logger.info(f"Joined guild: {guild.name} ({guild.id})")
    
    async def on_guild_remove(self, guild):
        """Called when bot leaves a guild"""
        logger.info(f"Left guild: {guild.name} ({guild.id})")

async def main():
    """Main function to run the bot"""
    bot = ModBot()
    await bot.load_extension("messagelogger")
    await bot.load_extension("invite")
    await bot.load_extension("xoxo")

    # Check if token exists
    if not Config.BOT_TOKEN:
        logger.error("DISCORD_TOKEN environment variable is not set!")
        return

    try:
        await bot.start(Config.BOT_TOKEN)  # now it's inside async function
    except discord.LoginFailure:
        logger.error("Invalid bot token provided!")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

# Entry point
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
