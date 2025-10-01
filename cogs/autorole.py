import discord
from discord.ext import commands
import json
import os

AUTOROLE_FILE = "/data/autorole.json"

def load_autoroles():
    if not os.path.exists(AUTOROLE_FILE):
        return {}
    with open(AUTOROLE_FILE, "r") as f:
        return json.load(f)

def save_autoroles(data):
    with open(AUTOROLE_FILE, "w") as f:
        json.dump(data, f, indent=4)

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autoroles = load_autoroles()  # {guild_id: {"human": role_id, "bot": role_id}}

    @commands.command(name="autorole", aliases=["joinrole"])
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx, type_: str = None, role: discord.Role = None):
        """Set autorole for humans or bots"""
        if type_ is None or role is None:
            return await ctx.send(
                "‼️ Specify your type and role!\nExample:\n`$autorole human/bot @role`"
            )

        type_ = type_.lower()
        if type_ not in ["human", "bot"]:
            return await ctx.send("❌ Invalid type! Use `human` or `bot`.")

        guild_id = str(ctx.guild.id)
        if guild_id not in self.autoroles:
            self.autoroles[guild_id] = {}

        self.autoroles[guild_id][type_] = role.id
        save_autoroles(self.autoroles)

        await ctx.send(f"✅ Set autorole for **{type_}** to {role.mention}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild_id = str(member.guild.id)
        if guild_id not in self.autoroles:
            return

        role_id = None
        if member.bot and "bot" in self.autoroles[guild_id]:
            role_id = self.autoroles[guild_id]["bot"]
        elif not member.bot and "human" in self.autoroles[guild_id]:
            role_id = self.autoroles[guild_id]["human"]

        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass  # bot can't assign role
