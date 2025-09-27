import os
import json

class Config:
    """Configuration class for the bot with per-server prefixes"""

    # Bot token - prioritize environment variable
    BOT_TOKEN = os.getenv("DISCORD_TOKEN")

    # Default prefix
    DEFAULT_PREFIX = "$"

    # Bot settings
    MAX_MESSAGE_DELETE = 1000
    DEFAULT_MUTE_DURATION = 3600  # 1 hour

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

    # Prefix storage file
    PREFIX_FILE = "/data/prefixes.json"

    # In-memory cache of prefixes
    _prefix_cache = {}

    @classmethod
    def load_prefixes(cls):
        """Load prefixes from JSON file into cache."""
        if not os.path.exists(cls.PREFIX_FILE):
            with open(cls.PREFIX_FILE, "w") as f:
                json.dump({}, f)
        with open(cls.PREFIX_FILE, "r") as f:
            cls._prefix_cache = json.load(f)

    @classmethod
    def save_prefixes(cls):
        """Save cached prefixes to JSON file."""
        with open(cls.PREFIX_FILE, "w") as f:
            json.dump(cls._prefix_cache, f, indent=4)

    @classmethod
    def get_prefix(cls, guild_id):
        """Return prefix for a guild, default if not set."""
        return cls._prefix_cache.get(str(guild_id), cls.DEFAULT_PREFIX)

    @classmethod
    def set_prefix(cls, guild_id, new_prefix):
        """Set a new prefix for a guild."""
        cls._prefix_cache[str(guild_id)] = new_prefix
        cls.save_prefixes()