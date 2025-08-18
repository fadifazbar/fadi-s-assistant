import os

class Config:
    """Configuration class for the bot"""
    
    # Bot token - prioritize environment variable, fallback to provided token
    BOT_TOKEN = os.getenv("DISCORD_TOKEN", "MTQwNjY0MTM3NTY0MTk5MzMxNw.GYu7RH.OMohbI8X87eFriP4PpMVUKxOz_SufkOTftIv2U")
    
    # Command prefix
    PREFIX = "$"
    
    # Bot settings
    MAX_MESSAGE_DELETE = 100  # Maximum messages to delete at once
    DEFAULT_MUTE_DURATION = 3600  # Default mute duration in seconds (1 hour)
    
    # Logging settings
    LOG_LEVEL = "INFO"
    LOG_FILE = "bot.log"
    
    # Colors for embeds
    COLORS = {
        "success": 0x00ff00,
        "error": 0xff0000,
        "warning": 0xffff00,
        "info": 0x0099ff,
        "moderation": 0xff6600
    }
