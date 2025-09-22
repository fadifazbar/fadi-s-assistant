# cogs/logging.py
import discord
from discord.ext import commands
from discord import app_commands, ui
import os, json, difflib
from datetime import datetime  # fixed typo

DATA_FILE = "/data/logs.json"


# ======================
# Persistence
# ======================
def load_config():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ log_config.json corrupted, resetting file...")
            return {}
    return {}


def save_config(config):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"💾 Saved logging config ({len(config)} guilds).")
    except Exception as e:
        print(f"❌ Failed to save logging config: {e}")


# ======================
# Logging Cog
# ======================
class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.valid_categories = {
    "messages": "💬 Messages",
    "members": "👥 Members",
    "roles": "🎭 Roles",
    "channels": "📢 Channels",
    "moderation": "🛡️ Moderation",
    "voice": "🔊 Voice",
    "server": "🛠️ Server Settings",
    "bots": "🤖 Bots & Integrations",
    "threads": "🧵 Threads",
    "emojis": "😃 Emojis & Stickers"
}

    # ----------------------
    # Helpers
    # ----------------------
    def fuzzy_category(self, query: str) -> str | None:
        query = query.lower()
        matches = difflib.get_close_matches(query, self.valid_categories, n=1, cutoff=0.3)
        return matches[0] if matches else None

    def _set_channel(self, guild: discord.Guild, category: str, channel_id: int) -> None:
        gid = str(guild.id)
        if gid not in self.config:
            self.config[gid] = {}
        # Always replace old channel with the new one
        self.config[gid][category] = channel_id
        save_config(self.config)

    def _get_channel(self, guild: discord.Guild, category: str) -> discord.TextChannel | None:
        gid = str(guild.id)
        cid = self.config.get(gid, {}).get(category)
        return guild.get_channel(cid) if cid else None

    async def send_log(self, guild: discord.Guild, category: str, embed: discord.Embed) -> None:
        channel = self._get_channel(guild, category)
        if not channel:
            return

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.NotFound):
            # Bot lost perms or channel deleted → remove from config
            gid = str(guild.id)
            if gid in self.config and category in self.config[gid]:
                del self.config[gid][category]
                save_config(self.config)
                print(f"⚠️ Removed invalid log channel for {category} in guild {guild.id}")
        except discord.HTTPException:
            # Something went wrong sending the message → ignore
            pass

    # ----------------------
    # Commands
    # ----------------------
    @commands.command(name="setlog")
    @commands.has_permissions(manage_guild=True)
    async def setlog_prefix(self, ctx, category: str, channel: discord.TextChannel):
        closest = self.fuzzy_category(category)
        if not closest:
            return await ctx.send(
                f"❌ Invalid category. Valid options: {', '.join(self.valid_categories)}"
            )

        self._set_channel(ctx.guild, closest, channel.id)
        await ctx.send(
            f"✅ {closest.capitalize()} logs are now set to {channel.mention} "
            f"(old channel replaced if there was one)."
        )

    @app_commands.command(name="setlog", description="Set a logging channel for a category")
    @app_commands.describe(
        category="The log category (messages, members, roles, channels, etc.)",
        channel="The channel where logs will be sent"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlog_slash(self, interaction: discord.Interaction, category: str, channel: discord.TextChannel):
        closest = self.fuzzy_category(category)
        if not closest:
            return await interaction.response.send_message(
                f"❌ Invalid category. Valid options: {', '.join(self.valid_categories)}",
                ephemeral=True
            )

        self._set_channel(interaction.guild, closest, channel.id)
        await interaction.response.send_message(
            f"✅ {closest.capitalize()} logs are now set to {channel.mention} "
            f"(old channel replaced if there was one)."
        )

    @setlog_slash.autocomplete("category")
    async def setlog_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=c.capitalize(), value=c)
            for c in self.valid_categories
            if current.lower() in c.lower()
        ][:25]


    # ----------------------
    # Events
    # ----------------------


    # ----------------------
    # Bot / Integration Events
    # ----------------------
    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(
            title="🤖 Webhook Updated",
            description=f"A webhook was added/removed/edited in {channel.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(channel.guild, "bots", embed)

    # ----------------------
    # Emoji & Sticker Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]):
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]

        if added or removed:
            changes = []
            if added:
                changes.append("➕ Added: " + ", ".join(str(e) for e in added))
            if removed:
                changes.append("➖ Removed: " + ", ".join(str(e) for e in removed))

            embed = discord.Embed(
                title="😃 Emojis Updated",
                description="\n".join(changes),
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            await self.send_log(guild, "emojis", embed)

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before: list[discord.Sticker], after: list[discord.Sticker]):
        added = [s for s in after if s not in before]
        removed = [s for s in before if s not in after]

        if added or removed:
            changes = []
            if added:
                changes.append("➕ Added: " + ", ".join(s.name for s in added))
            if removed:
                changes.append("➖ Removed: " + ", ".join(s.name for s in removed))

            embed = discord.Embed(
                title="🎟️ Stickers Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            await self.send_log(guild, "emojis", embed)

    # ----------------------
    # Thread Events
    # ----------------------
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        embed = discord.Embed(
            title="🧵 Thread Created",
            description=f"{thread.mention} ({thread.name})",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(thread.guild, "threads", embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        embed = discord.Embed(
            title="🧵 Thread Deleted",
            description=f"{thread.name}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(thread.guild, "threads", embed)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if before.name != after.name:
            embed = discord.Embed(
                title="🧵 Thread Renamed",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Before", value=before.name, inline=True)
            embed.add_field(name="After", value=after.name, inline=True)
            await self.send_log(after.guild, "threads", embed)

    # ----------------------
    # Message Events
    # ----------------------
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        content = message.content or "*No content*"
        embed.add_field(name="Content", value=content[:1024], inline=False)

        await self.send_log(message.guild, "messages", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*Empty*", inline=False)

        await self.send_log(before.guild, "messages", embed)

    # ----------------------
    # Member Events
    # ----------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(
            title="👤 Member Joined",
            description=f"{member.mention} ({member})",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(member.guild, "members", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(
            title="👤 Member Left",
            description=f"{member.mention} ({member})",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(member.guild, "members", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = discord.Embed(
                title="📝 Nickname Changed",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=after.mention, inline=True)
            embed.add_field(name="Before", value=before.nick or "*None*", inline=True)
            embed.add_field(name="After", value=after.nick or "*None*", inline=True)
            await self.send_log(after.guild, "members", embed)

        if before.roles != after.roles:
            before_roles = ", ".join(r.mention for r in before.roles if r.name != "@everyone")
            after_roles = ", ".join(r.mention for r in after.roles if r.name != "@everyone")
            embed = discord.Embed(
                title="🎭 Roles Updated",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=after.mention, inline=False)
            embed.add_field(name="Before", value=before_roles or "*None*", inline=False)
            embed.add_field(name="After", value=after_roles or "*None*", inline=False)
            await self.send_log(after.guild, "members", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"{user.mention} ({user})",
            color=discord.Color.dark_red(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(guild, "members", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = discord.Embed(
            title="⚖️ Member Unbanned",
            description=f"{user.mention} ({user})",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(guild, "members", embed)

    # ----------------------
    # Channel Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(
            title="📢 Channel Created",
            description=f"{channel.mention} ({channel.name})",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(channel.guild, "channels", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(
            title="📢 Channel Deleted",
            description=f"{channel.name}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(channel.guild, "channels", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        if before.name != after.name:
            embed = discord.Embed(
                title="📢 Channel Renamed",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Before", value=before.name, inline=True)
            embed.add_field(name="After", value=after.name, inline=True)
            await self.send_log(after.guild, "channels", embed)

    # ----------------------
    # Role Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = discord.Embed(
            title="🎭 Role Created",
            description=f"{role.mention} ({role.name})",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(role.guild, "roles", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = discord.Embed(
            title="🎭 Role Deleted",
            description=f"{role.name}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await self.send_log(role.guild, "roles", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.permissions != after.permissions:
            changes.append("**Permissions Updated**")
        if before.color != after.color:
            changes.append(f"**Color:** {before.color} → {after.color}")

        if changes:
            embed = discord.Embed(
                title="🎭 Role Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Role", value=after.mention, inline=False)
            await self.send_log(after.guild, "roles", embed)

    # ----------------------
    # Guild Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.icon != after.icon:
            changes.append("**Icon Updated**")
        if before.banner != after.banner:
            changes.append("**Banner Updated**")
        if before.owner_id != after.owner_id:
            before_owner = before.get_member(before.owner_id)
            after_owner = after.get_member(after.owner_id)
            changes.append(f"**Owner:** {before_owner} → {after_owner}")

        if changes:
            embed = discord.Embed(
                title="🏰 Server Updated",
                description="\n".join(changes),
                color=discord.Color.teal(),
                timestamp=datetime.utcnow()
            )
            await self.send_log(after, "guild", embed)

    # ----------------------
    # Voice State Events
    # ----------------------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        changes = []

        if before.channel != after.channel:
            if before.channel is None and after.channel is not None:
                changes.append(f"🎙️ Joined voice channel: {after.channel.mention}")
            elif before.channel is not None and after.channel is None:
                changes.append(f"📤 Left voice channel: {before.channel.mention}")
            else:
                changes.append(f"🔄 Moved: {before.channel.mention} → {after.channel.mention}")

        if before.mute != after.mute:
            changes.append(f"🔇 Server mute: {before.mute} → {after.mute}")
        if before.deaf != after.deaf:
            changes.append(f"🔈 Server deaf: {before.deaf} → {after.deaf}")
        if before.self_mute != after.self_mute:
            changes.append(f"🎙️ Self mute: {before.self_mute} → {after.self_mute}")
        if before.self_deaf != after.self_deaf:
            changes.append(f"🎧 Self deaf: {before.self_deaf} → {after.self_deaf}")
        if before.self_stream != after.self_stream:
            changes.append(f"📺 Streaming: {before.self_stream} → {after.self_stream}")
        if before.self_video != after.self_video:
            changes.append(f"📹 Video: {before.self_video} → {after.self_video}")

        if changes:
            embed = discord.Embed(
                title="🔊 Voice State Updated",
                description="\n".join(changes),
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=member.mention, inline=False)
            await self.send_log(member.guild, "voice", embed)

    # ----------------------
    # Log settings viewer
    # ----------------------
    @commands.command(name="logsettings")
    @commands.has_permissions(manage_guild=True)
    async def logsettings_prefix(self, ctx):
        await self.show_logsettings(ctx, ctx.guild)

    @app_commands.command(name="logsettings", description="View current log channel settings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def logsettings_slash(self, interaction: discord.Interaction):
        await self.show_logsettings(interaction, interaction.guild)

    async def show_logsettings(self, src, guild: discord.Guild):
        gid = str(guild.id)
        guild_config = self.config.get(gid, {})
        categories = list(self.valid_categories.keys())
        page = 0

        def make_embed(page: int):
            cat = categories[page]
            channel = guild.get_channel(guild_config.get(cat, 0))
            embed = discord.Embed(
                title="⚙️ Log Settings",
                description=(
                    f"**Category:** {cat.capitalize()}\n"
                    f"**Channel:** {channel.mention if channel else '❌ Not set'}"
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Page {page+1}/{len(categories)}")
            return embed

        class SettingsView(ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary)
            async def back(self, interaction, button):
                nonlocal page
                if interaction.user != (src.user if isinstance(src, discord.Interaction) else src.author):
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                if page > 0:
                    page -= 1
                    await interaction.response.edit_message(embed=make_embed(page), view=self)

            @ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            async def forward(self, interaction, button):
                nonlocal page
                if interaction.user != (src.user if isinstance(src, discord.Interaction) else src.author):
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                if page < len(categories) - 1:
                    page += 1
                    await interaction.response.edit_message(embed=make_embed(page), view=self)

        if isinstance(src, discord.Interaction):
            await src.response.send_message(embed=make_embed(page), view=SettingsView(), ephemeral=True)
        else:
            await src.send(embed=make_embed(page), view=SettingsView())


async def setup(bot):
    await bot.add_cog(LoggingCog(bot))