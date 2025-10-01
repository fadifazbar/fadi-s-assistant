import discord
from discord.ext import commands
import json, os, asyncio

AUTOROLE_FILE = "/data/autorole.json"

def load_autoroles():
    if not os.path.exists(AUTOROLE_FILE):
        return {}
    try:
        with open(AUTOROLE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_autoroles(data: dict):
    with open(AUTOROLE_FILE, "w") as f:
        json.dump(data, f, indent=4)

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autoroles = load_autoroles()  # {guild_id: {"human": role_id, "bot": role_id, "invites": {invite_code: role_id}}}
        self.invite_cache = {}  # {guild_id: {invite_code: uses}}

    async def cache_invites(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            self.invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}
        except discord.Forbidden:
            self.invite_cache[guild.id] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        # Cache invites for all guilds
        for guild in self.bot.guilds:
            await self.cache_invites(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.cache_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        await self.cache_invites(invite.guild)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        await self.cache_invites(invite.guild)

    # === COMMAND GROUP ===
    @commands.group(name="autorole", aliases=["joinrole"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx):
        await ctx.send("⚙️ Usage:\n"
                       "`$autorole set human/bot @role`\n"
                       "`$autorole list`\n"
                       "`$autorole clear human/bot`\n"
                       "`$autorole invite <invite_url> @role`")

    @autorole.command(name="invite")
    @commands.has_permissions(administrator=True)
    async def autorole_invite(self, ctx, invite_url: str = None, role: discord.Role = None):
        """Set autorole for members joining via a specific invite"""
        if not invite_url or not role:
            return await ctx.send("‼️ Usage: `$autorole invite <invite_url> @role`")

        try:
            invite = await self.bot.fetch_invite(invite_url)
        except Exception:
            return await ctx.send("❌ Invalid invite URL.")

        guild_id = str(ctx.guild.id)
        self.autoroles.setdefault(guild_id, {}).setdefault("invites", {})
        self.autoroles[guild_id]["invites"][invite.code] = role.id
        save_autoroles(self.autoroles)

        await ctx.send(f"✅ Set autorole for invite `{invite.code}` → {role.mention}")

    # === MEMBER JOIN HANDLER ===
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        guild_id = str(guild.id)
        if guild_id not in self.autoroles:
            return

        role_id = None

        # Check invite usage
        try:
            before = self.invite_cache.get(guild.id, {})
            invites = await guild.invites()
            self.invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}

            used_invite = None
            for inv in invites:
                if inv.code in before and inv.uses > before[inv.code]:
                    used_invite = inv.code
                    break

            if used_invite:
                invite_roles = self.autoroles[guild_id].get("invites", {})
                if used_invite in invite_roles:
                    role_id = invite_roles[used_invite]
        except discord.Forbidden:
            pass

        # Fallback: normal human/bot autorole
        if not role_id:
            if member.bot and "bot" in self.autoroles[guild_id]:
                role_id = self.autoroles[guild_id]["bot"]
            elif not member.bot and "human" in self.autoroles[guild_id]:
                role_id = self.autoroles[guild_id]["human"]

        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="AutoRole assignment")
                except discord.Forbidden:
                    print(f"[AutoRole] Missing permissions to assign {role.name} in {guild.name}")
                except Exception as e:
                    print(f"[AutoRole] Failed to assign role {role_id} in {guild.name}: {e}")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))
    
