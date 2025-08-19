import discord
from discord.ext import commands
from discord import app_commands
import json
import os

REACTION_ROLE_FILE = "reaction_roles.json"

def load_reaction_roles():
    if not os.path.exists(REACTION_ROLE_FILE):
        return {}
    try:
        with open(REACTION_ROLE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_reaction_roles(data):
    with open(REACTION_ROLE_FILE, "w") as f:
        json.dump(data, f, indent=4)

reaction_roles = load_reaction_roles()

class ReactionRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------- Prefix Command ----------------
    @commands.command(name="reactionrole")
    @commands.has_permissions(manage_roles=True)
    async def reactionrole_prefix(self, ctx, message_id: int, emoji: str, role: discord.Role):
        # Check hierarchy against user
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot create a reaction role with a role higher or equal to your top role.")

        # Check hierarchy against bot
        if role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot manage that role because it is higher than or equal to my top role.")

        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("❌ Message not found.")

        await message.add_reaction(emoji)

        guild_id = str(ctx.guild.id)
        if guild_id not in reaction_roles:
            reaction_roles[guild_id] = {}
        if str(message_id) not in reaction_roles[guild_id]:
            reaction_roles[guild_id][str(message_id)] = {}

        # Allow multiple emojis per message
        reaction_roles[guild_id][str(message_id)][emoji] = role.id
        save_reaction_roles(reaction_roles)

        await ctx.send(f"✅ Reaction role set: {emoji} → {role.mention} on [this message]({message.jump_url})")

    # ---------------- Slash Command ----------------
    @app_commands.command(name="reactionrole", description="Set a reaction role on a message")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_slash(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        # Check hierarchy against user
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ You cannot create a reaction role with a role higher or equal to your top role.", ephemeral=True)

        # Check hierarchy against bot
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ I cannot manage that role because it is higher than or equal to my top role.", ephemeral=True)

        try:
            message = await interaction.channel.fetch_message(int(message_id))
        except discord.NotFound:
            return await interaction.response.send_message("❌ Message not found.", ephemeral=True)

        await message.add_reaction(emoji)

        guild_id = str(interaction.guild.id)
        if guild_id not in reaction_roles:
            reaction_roles[guild_id] = {}
        if str(message_id) not in reaction_roles[guild_id]:
            reaction_roles[guild_id][str(message_id)] = {}

        # Allow multiple emojis per message
        reaction_roles[guild_id][str(message_id)][emoji] = role.id
        save_reaction_roles(reaction_roles)

        await interaction.response.send_message(
            f"✅ Reaction role set: {emoji} → {role.mention} on [this message]({message.jump_url})",
            ephemeral=False
        )

    # ---------------- Event: Add Role ----------------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        guild_data = reaction_roles.get(str(guild.id), {})
        msg_roles = guild_data.get(str(payload.message_id), {})
        role_id = msg_roles.get(str(payload.emoji))
        if not role_id:
            return

        role = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member and not member.bot:
            try:
                await member.add_roles(role, reason="Reaction role")
            except discord.Forbidden:
                pass  # Ignore missing permissions

    # ---------------- Event: Remove Role ----------------
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        guild_data = reaction_roles.get(str(guild.id), {})
        msg_roles = guild_data.get(str(payload.message_id), {})
        role_id = msg_roles.get(str(payload.emoji))
        if not role_id:
            return

        role = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member and not member.bot:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except discord.Forbidden:
                pass  # Ignore missing permissions

async def setup(bot):
    await bot.add_cog(ReactionRole(bot))
