import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
import datetime

# ---------------- File Path ----------------
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "security_config.json")

# ---------------- JSON Helpers ----------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------- Cog ----------------
class Security(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()
        self.recent_joins = {}
        self.recent_actions = {}

    # ---------------- Utils ----------------
    def ensure_guild(self, guild_id):
        if str(guild_id) not in self.config:
            self.config[str(guild_id)] = {
                "blacklist": [],
                "whitelist": [],
                "features": {
                    "suspicious": True,
                    "antinuke": True,
                    "raidalert": True,
                    "autolock": True
                },
                "thresholds": {
                    "joins": {"limit": 10, "time": 10, "action": "lockdown"},
                    "antinuke": {"limit": 3, "time": 10, "action": "ban"}
                },
                "account_age": 7 # days
            }
        return self.config[str(guild_id)]

    async def apply_action(self, guild, member, action):
        try:
            if action == "kick":
                await member.kick(reason="Security System")
            elif action == "ban":
                await member.ban(reason="Security System")
            elif action == "lockdown":
                overwrites = discord.PermissionOverwrite(send_messages=False)
                for channel in guild.text_channels:
                    await channel.set_permissions(guild.default_role, overwrite=overwrites)
        except:
            pass

    # ---------------- Events ----------------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        settings = self.ensure_guild(guild.id)

        # Blacklist check
        if member.id in settings["blacklist"]:
            await member.kick(reason="Blacklisted")
            return

        # Whitelist check for bots
        if member.bot and member.id not in settings["whitelist"]:
            await member.kick(reason="Bot not whitelisted")
            return

        # Suspicious account detection
        if settings["features"]["suspicious"]:
            min_age = datetime.timedelta(days=settings["account_age"])
            if (discord.utils.utcnow() - member.created_at) < min_age:
                await member.kick(reason="Suspicious account (too new)")
                return

        # Join threshold check
        if settings["features"]["autolock"]:
            now = discord.utils.utcnow().timestamp()
            joins = self.recent_joins.get(guild.id, [])
            joins = [j for j in joins if now - j < settings["thresholds"]["joins"]["time"]]
            joins.append(now)
            self.recent_joins[guild.id] = joins

            if len(joins) >= settings["thresholds"]["joins"]["limit"]:
                action = settings["thresholds"]["joins"]["action"]
                await self.apply_action(guild, member, action)
                owner = guild.owner
                if owner:
                    await owner.send(f"⚠️ Raid detected in {guild.name}! Action: {action}")

    # ---------------- Commands ----------------
    @commands.hybrid_command(name="blacklist_add")
    async def blacklist_add(self, ctx, user_id: int):
        settings = self.ensure_guild(ctx.guild.id)
        if user_id not in settings["blacklist"]:
            settings["blacklist"].append(user_id)
            save_config(self.config)
            await ctx.send(f"✅ Added {user_id} to blacklist")

    @commands.hybrid_command(name="blacklist_remove")
    async def blacklist_remove(self, ctx, user_id: int):
        settings = self.ensure_guild(ctx.guild.id)
        if user_id in settings["blacklist"]:
            settings["blacklist"].remove(user_id)
            save_config(self.config)
            await ctx.send(f"✅ Removed {user_id} from blacklist")

    @commands.hybrid_command(name="whitelist_add")
    async def whitelist_add(self, ctx, user_id: int):
        settings = self.ensure_guild(ctx.guild.id)
        if user_id not in settings["whitelist"]:
            settings["whitelist"].append(user_id)
            save_config(self.config)
            await ctx.send(f"✅ Added {user_id} to whitelist")

    @commands.hybrid_command(name="whitelist_remove")
    async def whitelist_remove(self, ctx, user_id: int):
        settings = self.ensure_guild(ctx.guild.id)
        if user_id in settings["whitelist"]:
            settings["whitelist"].remove(user_id)
            save_config(self.config)
            await ctx.send(f"✅ Removed {user_id} from whitelist")

    @commands.hybrid_command(name="thresholds")
    @commands.has_permissions(administrator=True)
    async def thresholds(self, ctx, action: str, limit: int, time: int, punishment: str):
        settings = self.ensure_guild(ctx.guild.id)
        if action not in settings["thresholds"]:
            await ctx.send("❌ Invalid action. Available: joins, antinuke")
            return
        settings["thresholds"][action] = {"limit": limit, "time": time, "action": punishment}
        save_config(self.config)
        await ctx.send(f"✅ Threshold for {action} updated → {limit} in {time}s → {punishment}")

    @commands.hybrid_command(name="lockdown")
    @commands.has_permissions(administrator=True)
    async def lockdown(self, ctx):
        overwrites = discord.PermissionOverwrite(send_messages=False)
        for channel in ctx.guild.text_channels:
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
        await ctx.send("🔒 Server locked down")

    @commands.hybrid_command(name="unlockdown")
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx):
        for channel in ctx.guild.text_channels:
            await channel.set_permissions(ctx.guild.default_role, overwrite=None)
        await ctx.send("🔓 Server unlocked")

async def setup(bot: commands.Bot):
    await bot.add_cog(Security(bot))
