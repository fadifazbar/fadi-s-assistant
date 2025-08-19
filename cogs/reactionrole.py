import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# ---------------- File Path (always in project root, next to bot.py) ----------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REACTION_ROLE_FILE = os.path.join(ROOT_DIR, "reaction_roles.json")


# ---------------- JSON Helpers ----------------
def load_reaction_roles():
    """Load reaction roles from JSON, or create the file if missing/broken."""
    if not os.path.exists(REACTION_ROLE_FILE):
        with open(REACTION_ROLE_FILE, "w") as f:
            json.dump({}, f, indent=4)
        return {}

    try:
        with open(REACTION_ROLE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_reaction_roles(data: dict):
    """Save reaction roles safely to JSON."""
    with open(REACTION_ROLE_FILE, "w") as f:
        json.dump(data, f, indent=4)


reaction_roles = load_reaction_roles()


# ---------------- Cog ----------------
class ReactionRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Helper: convert emoji to string (handles custom + unicode)
    def emoji_to_str(self, emoji: discord.PartialEmoji | str):
        return str(emoji)

    # ---------------- Prefix Command ----------------
    @commands.command(name="reactionrole")
    @commands.has_permissions(manage_roles=True)
    async def reactionrole_prefix(self, ctx, message_id: int, emoji: str, role: discord.Role):
        """Create a reaction role using a prefix command."""
        # Check hierarchy against user
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot create a reaction role with a role higher or equal to your top role.")

        # Check hierarchy against bot
        if role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot manage that role because it is higher than or equal to my top role.")

        # Fetch message
        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("❌ Message not found.")
        except discord.Forbidden:
            return await ctx.send("❌ I don’t have permission to fetch that message.")

        # Add reaction
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await ctx.send("❌ Invalid emoji.")

        # Save to JSON
        guild_id = str(ctx.guild.id)
        emoji_str = str(emoji)
        reaction_roles.setdefault(guild_id, {}).setdefault(str(message_id), {})
        reaction_roles[guild_id][str(message_id)][emoji_str] = role.id
        save_reaction_roles(reaction_roles)

        await ctx.send(f"✅ Reaction role set: {emoji} → {role.mention} on [this message]({message.jump_url})")

    # ---------------- Slash Command ----------------
    @app_commands.command(name="reactionrole", description="Set a reaction role on a message")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_slash(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        """Create a reaction role using a slash command."""
        # Check hierarchy against user
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message(
                "❌ You cannot create a reaction role with a role higher or equal to your top role.",
                ephemeral=True
            )

        # Check hierarchy against bot
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "❌ I cannot manage that role because it is higher than or equal to my top role.",
                ephemeral=True
            )

        # Fetch message
        try:
            message = await interaction.channel.fetch_message(int(message_id))
        except discord.NotFound:
            return await interaction.response.send_message("❌ Message not found.", ephemeral=True)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ I don’t have permission to fetch that message.", ephemeral=True)

        # Add reaction
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await interaction.response.send_message("❌ Invalid emoji.", ephemeral=True)

        # Save to JSON
        guild_id = str(interaction.guild.id)
        emoji_str = str(emoji)
        reaction_roles.setdefault(guild_id, {}).setdefault(str(message_id), {})
        reaction_roles[guild_id][str(message_id)][emoji_str] = role.id
        save_reaction_roles(reaction_roles)

        await interaction.response.send_message(
            f"✅ Reaction role set: {emoji} → {role.mention} on [this message]({message.jump_url})"
        )

    # ---------------- Debug Command (List) ----------------
    @commands.command(name="reactionrolelist")
    @commands.has_permissions(manage_roles=True)
    async def reactionrole_list(self, ctx):
        """List all reaction roles set in the server."""
        guild_data = reaction_roles.get(str(ctx.guild.id), {})
        if not guild_data:
            return await ctx.send("ℹ️ No reaction roles set in this server.")

        msg = "📌 **Reaction Roles in this server:**\n"
        for msg_id, emojis in guild_data.items():
            msg += f"\nMessage `{msg_id}`:\n"
            for emoji, role_id in emojis.items():
                role = ctx.guild.get_role(role_id)
                msg += f"  {emoji} → {role.mention if role else '(deleted role)'}\n"

        await ctx.send(msg)

    # ---------------- Event: Add Role ----------------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        guild_data = reaction_roles.get(str(guild.id), {})
        msg_roles = guild_data.get(str(payload.message_id), {})
        emoji_str = str(payload.emoji)
        role_id = msg_roles.get(emoji_str)
        if not role_id:
            return

        role = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member and not member.bot:
            try:
                await member.add_roles(role, reason="Reaction role")
            except discord.Forbidden:
                print(f"[WARN] Missing permissions to give {role} in {guild.name}")

    # ---------------- Event: Remove Role ----------------
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        guild_data = reaction_roles.get(str(guild.id), {})
        msg_roles = guild_data.get(str(payload.message_id), {})
        emoji_str = str(payload.emoji)
        role_id = msg_roles.get(emoji_str)
        if not role_id:
            return

        role = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member and not member.bot:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except discord.Forbidden:
                print(f"[WARN] Missing permissions to remove {role} in {guild.name}")


# ---------------- Cog Setup ----------------
async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))
