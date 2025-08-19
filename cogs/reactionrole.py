import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "reaction_roles.json"

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reaction_roles = self.load_config()

    # --------------------------
    # CONFIG MANAGEMENT
    # --------------------------
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}  # {guild_id: {message_id: {emoji: role_id}}}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.reaction_roles, f, indent=4)

    def add_reaction_role(self, guild_id, message_id, emoji, role_id):
        guild_id, message_id, emoji = str(guild_id), str(message_id), str(emoji)
        if guild_id not in self.reaction_roles:
            self.reaction_roles[guild_id] = {}
        if message_id not in self.reaction_roles[guild_id]:
            self.reaction_roles[guild_id][message_id] = {}
        self.reaction_roles[guild_id][message_id][emoji] = role_id
        self.save_config()

    def get_role_id(self, guild_id, message_id, emoji):
        return self.reaction_roles.get(str(guild_id), {}).get(str(message_id), {}).get(str(emoji))

    # --------------------------
    # PREFIX COMMAND
    # --------------------------
    @commands.command(name="reactionrole")
    @commands.has_permissions(manage_roles=True)
    async def reactionrole_prefix(self, ctx, message_id: int, emoji: str, role: discord.Role):
        """Create a reaction role (prefix version)"""
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot create a reaction role with a role higher or equal to your top role.")

        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("❌ Message not found.")

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await ctx.send("❌ Invalid emoji.")

        self.add_reaction_role(ctx.guild.id, message.id, emoji, role.id)
        await ctx.send(f"✅ Reaction role created: React with {emoji} to get {role.mention}")

    # --------------------------
    # SLASH COMMAND
    # --------------------------
    @app_commands.command(name="reactionrole", description="Create a reaction role on a message")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_slash(self, interaction: discord.Interaction, messageid: str, emoji: str, role: discord.Role):
        """Create a reaction role (slash version)"""
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message(
                "❌ You cannot create a reaction role with a role higher or equal to your top role.",
                ephemeral=True
            )

        try:
            message = await interaction.channel.fetch_message(int(messageid))
        except discord.NotFound:
            return await interaction.response.send_message("❌ Message not found.", ephemeral=True)

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await interaction.response.send_message("❌ Invalid emoji.", ephemeral=True)

        self.add_reaction_role(interaction.guild.id, message.id, emoji, role.id)
        await interaction.response.send_message(
            f"✅ Reaction role created: React with {emoji} to get {role.mention}",
            ephemeral=True
        )

    # --------------------------
    # LISTENERS
    # --------------------------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        role_id = self.get_role_id(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(role_id)
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if member and not member.bot:
            try:
                await member.add_roles(role, reason="Reaction role")
            except discord.Forbidden:
                pass  # bot missing perms

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        role_id = self.get_role_id(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(role_id)
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if member and not member.bot:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except discord.Forbidden:
                pass  # bot missing perms

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
