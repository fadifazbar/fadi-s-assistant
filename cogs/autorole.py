import discord
from discord.ext import commands
import json
import os

AUTOROLE_FILE = "/data/autorole.json"


def load_autoroles():
    if not os.path.exists(AUTOROLE_FILE):
        return {}
    try:
        with open(AUTOROLE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Reset if file is corrupted
        return {}


def save_autoroles(data: dict):
    with open(AUTOROLE_FILE, "w") as f:
        json.dump(data, f, indent=4)


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autoroles = load_autoroles()  # {guild_id: {"human": role_id, "bot": role_id}}

    # === COMMAND GROUP ===
    @commands.group(name="autorole", aliases=["joinrole"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx):
        """Manage autoroles. Subcommands: set, list, clear"""
        await ctx.send(
            "⚙️ Usage:\n"
            "`$autorole set human @role`\n"
            "`$autorole set bot @role`\n"
            "`$autorole list`\n"
            "`$autorole clear human/bot`"
        )

    @autorole.command(name="set")
    @commands.has_permissions(administrator=True)
    async def autorole_set(self, ctx, type_: str = None, role: discord.Role = None):
        """Set autorole for humans or bots"""
        if type_ is None or role is None:
            return await ctx.send("‼️ Usage: `$autorole set human/bot @role`")

        type_ = type_.lower()
        if type_ not in ["human", "bot"]:
            return await ctx.send("❌ Invalid type! Use `human` or `bot`.")

        guild_id = str(ctx.guild.id)
        self.autoroles.setdefault(guild_id, {})[type_] = role.id
        save_autoroles(self.autoroles)

        await ctx.send(f"✅ Set autorole for **{type_}s** to {role.mention}")

    @autorole.command(name="list")
    @commands.has_permissions(administrator=True)
    async def autorole_list(self, ctx):
        """Show current autorole settings"""
        guild_id = str(ctx.guild.id)
        settings = self.autoroles.get(guild_id, {})

        human_role = ctx.guild.get_role(settings.get("human")) if "human" in settings else None
        bot_role = ctx.guild.get_role(settings.get("bot")) if "bot" in settings else None

        msg = (
            f"👤 Human autorole: {human_role.mention if human_role else 'None'}\n"
            f"🤖 Bot autorole: {bot_role.mention if bot_role else 'None'}"
        )
        await ctx.send(msg)

    @autorole.command(name="clear")
    @commands.has_permissions(administrator=True)
    async def autorole_clear(self, ctx, type_: str = None):
        """Clear autorole for humans or bots"""
        if type_ is None or type_.lower() not in ["human", "bot"]:
            return await ctx.send("‼️ Usage: `$autorole clear human/bot`")

        guild_id = str(ctx.guild.id)
        if guild_id in self.autoroles and type_.lower() in self.autoroles[guild_id]:
            del self.autoroles[guild_id][type_.lower()]
            save_autoroles(self.autoroles)
            await ctx.send(f"🗑️ Cleared autorole for {type_.lower()}s.")
        else:
            await ctx.send(f"⚠️ No autorole set for {type_.lower()}s.")

    # === LISTENER: Assign roles on join ===
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
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
                    await member.add_roles(role, reason="AutoRole assignment")
                except discord.Forbidden:
                    print(f"[AutoRole] Missing permissions to assign {role.name} in {member.guild.name}")
                except Exception as e:
                    print(f"[AutoRole] Failed to assign role {role_id} in {member.guild.name}: {e}")

    # === CLEANUP WHEN BOT LEAVES A GUILD ===
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        guild_id = str(guild.id)
        if guild_id in self.autoroles:
            del self.autoroles[guild_id]
            save_autoroles(self.autoroles)
            print(f"[AutoRole] Cleaned up settings for guild {guild.name} ({guild.id})")


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
        
