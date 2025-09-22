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
            "guild": "🏰 Server Updates",
            "bots": "🤖 Bots & Integrations",
            "threads": "🧵 Threads",
            "emojis": "😃 Emojis & Stickers",
            "invites": "📨 Invites",
            "webhooks": "🪝 Webhooks",
            "events": "📅 Scheduled Events"
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
        embed.add_field(name="Author", value=f"{message.author.mention} ({message.author})", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Author ID", value=message.author.id, inline=True)
        embed.add_field(name="Message ID", value=message.id, inline=True)

        content = message.content or "*No content*"
        embed.add_field(name="Content", value=content[:1024], inline=False)

        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Channel ID: {message.channel.id} | Guild ID: {message.guild.id}")

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
        embed.add_field(name="Author", value=f"{before.author.mention} ({before.author})", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Author ID", value=before.author.id, inline=True)
        embed.add_field(name="Message ID", value=before.id, inline=True)
        embed.add_field(name="Before", value=before.content[:1024] or "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "*Empty*", inline=False)

        embed.set_thumbnail(url=before.author.display_avatar.url)
        embed.set_footer(text=f"Channel ID: {before.channel.id} | Guild ID: {before.guild.id}")

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
        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style='R'), inline=True)

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Guild ID: {member.guild.id}")

        await self.send_log(member.guild, "members", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(
            title="👤 Member Left",
            description=f"{member.mention} ({member})",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Guild ID: {member.guild.id}")

        await self.send_log(member.guild, "members", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = discord.Embed(
                title="📝 Nickname Changed",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=after.mention, inline=False)
            embed.add_field(name="Before", value=before.nick or "*None*", inline=True)
            embed.add_field(name="After", value=after.nick or "*None*", inline=True)

            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"User ID: {after.id} | Guild ID: {after.guild.id}")

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

            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"User ID: {after.id} | Guild ID: {after.guild.id}")

            await self.send_log(after.guild, "members", embed)

    # ----------------------
    # Role Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        guild = role.guild
        moderator = "Unknown"

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    moderator = entry.user.mention
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="🎭 Role Created",
            description=f"{role.mention} ({role.name})",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Moderator", value=moderator, inline=True)
        embed.add_field(name="Role ID", value=role.id, inline=True)

        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        embed.set_footer(text=f"Guild ID: {guild.id}")

        await self.send_log(guild, "roles", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        moderator = "Unknown"

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    moderator = entry.user.mention
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="🎭 Role Deleted",
            description=f"{role.name}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Moderator", value=moderator, inline=True)
        embed.add_field(name="Role ID", value=role.id, inline=True)

        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        embed.set_footer(text=f"Guild ID: {guild.id}")

        await self.send_log(guild, "roles", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        guild = after.guild
        moderator = "Unknown"

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
                if entry.target.id == after.id:
                    moderator = entry.user.mention
                    break
        except discord.Forbidden:
            pass

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
            embed.add_field(name="Moderator", value=moderator, inline=False)
            embed.add_field(name="Role ID", value=after.id, inline=True)

            embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
            embed.set_footer(text=f"Guild ID: {guild.id}")

            await self.send_log(guild, "roles", embed)


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
                color=discord.Color.green() if added else discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
            embed.set_footer(text=f"Guild ID: {guild.id}")

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
                color=discord.Color.green() if added else discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
            embed.set_footer(text=f"Guild ID: {guild.id}")

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
        embed.add_field(name="Thread ID", value=thread.id, inline=True)
        embed.add_field(name="Parent Channel", value=thread.parent.mention, inline=True)

        embed.set_thumbnail(url=thread.guild.icon.url if thread.guild.icon else discord.Embed.Empty)
        embed.set_footer(text=f"Guild ID: {thread.guild.id}")

        await self.send_log(thread.guild, "threads", embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        embed = discord.Embed(
            title="🧵 Thread Deleted",
            description=f"{thread.name}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Thread ID", value=thread.id, inline=True)
        embed.add_field(name="Parent Channel", value=thread.parent.name, inline=True)

        embed.set_thumbnail(url=thread.guild.icon.url if thread.guild.icon else discord.Embed.Empty)
        embed.set_footer(text=f"Guild ID: {thread.guild.id}")

        await self.send_log(thread.guild, "threads", embed)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.archived != after.archived:
            changes.append(f"**Archived:** {before.archived} → {after.archived}")
        if before.locked != after.locked:
            changes.append(f"**Locked:** {before.locked} → {after.locked}")

        if changes:
            embed = discord.Embed(
                title="🧵 Thread Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Thread", value=after.mention, inline=False)
            embed.add_field(name="Thread ID", value=after.id, inline=True)

            embed.set_thumbnail(url=after.guild.icon.url if after.guild.icon else discord.Embed.Empty)
            embed.set_footer(text=f"Guild ID: {after.guild.id}")

            await self.send_log(after.guild, "threads", embed)


    # ----------------------
    # Channel Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        moderator = "Unknown"

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    moderator = entry.user.mention
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="📢 Channel Created",
            description=f"{channel.mention} ({channel.name})",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Type", value=str(channel.type).capitalize(), inline=True)
        embed.add_field(name="Moderator", value=moderator, inline=True)

        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        embed.set_footer(text=f"Channel ID: {channel.id} | Guild ID: {guild.id}")

        await self.send_log(guild, "channels", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        moderator = "Unknown"

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    moderator = entry.user.mention
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="📢 Channel Deleted",
            description=f"{channel.name}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Moderator", value=moderator, inline=True)

        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        embed.set_footer(text=f"Channel ID: {channel.id} | Guild ID: {guild.id}")

        await self.send_log(guild, "channels", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        guild = after.guild
        moderator = "Unknown"

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id:
                    moderator = entry.user.mention
                    break
        except discord.Forbidden:
            pass

        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.category != after.category:
            changes.append(f"**Category:** {before.category} → {after.category}")

        if changes:
            embed = discord.Embed(
                title="📢 Channel Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Moderator", value=moderator, inline=False)

            embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
            embed.set_footer(text=f"Channel ID: {after.id} | Guild ID: {guild.id}")

            await self.send_log(guild, "channels", embed)

    # ----------------------
    # Bot Events
    # ----------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            guild = member.guild
            moderator = "Unknown"

            try:
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                    if entry.target.id == member.id:
                        moderator = entry.user.mention
                        break
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                title="🤖 Bot Added",
                description=f"{member.mention} ({member.name}#{member.discriminator})",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Added By", value=moderator, inline=True)
            embed.add_field(name="Bot ID", value=member.id, inline=True)

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Guild ID: {guild.id}")

            await self.send_log(guild, "bots", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            guild = member.guild

            embed = discord.Embed(
                title="🤖 Bot Removed",
                description=f"{member.name}#{member.discriminator}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Bot ID", value=member.id, inline=True)

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Guild ID: {guild.id}")

            await self.send_log(guild, "bots", embed)


    # ----------------------
    # Server (Guild) Updates
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
        if before.afk_channel != after.afk_channel:
            changes.append(f"**AFK Channel:** {before.afk_channel} → {after.afk_channel}")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification Level:** {before.verification_level} → {after.verification_level}")

        if changes:
            embed = discord.Embed(
                title="🏛️ Server Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Server ID", value=after.id, inline=True)

            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
            embed.set_footer(text=f"Guild ID: {after.id}")

            await self.send_log(after, "server", embed)


    # ----------------------
    # Voice Events
    # ----------------------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild
        changes = []

        if before.channel != after.channel:
            if after.channel is None:
                changes.append(f"❌ Left {before.channel.mention}")
                color = discord.Color.red()
            elif before.channel is None:
                changes.append(f"✅ Joined {after.channel.mention}")
                color = discord.Color.green()
            else:
                changes.append(f"🔀 Moved {before.channel.mention} → {after.channel.mention}")
                color = discord.Color.orange()
        else:
            color = discord.Color.blurple()

        if before.mute != after.mute:
            changes.append(f"🔇 Mute: {before.mute} → {after.mute}")
        if before.deaf != after.deaf:
            changes.append(f"🔊 Deaf: {before.deaf} → {after.deaf}")
        if before.self_stream != after.self_stream:
            changes.append(f"📺 Streaming: {before.self_stream} → {after.self_stream}")
        if before.self_video != after.self_video:
            changes.append(f"📹 Camera: {before.self_video} → {after.self_video}")

        if changes:
            embed = discord.Embed(
                title="🎙️ Voice State Updated",
                description="\n".join(changes),
                color=color,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="User ID", value=member.id, inline=True)

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Guild ID: {guild.id}")

            await self.send_log(guild, "voice", embed)


    # ----------------------
    # Invite Events
    # ----------------------
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        guild = invite.guild
        embed = discord.Embed(
            title="📨 Invite Created",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Code", value=invite.code, inline=True)
        embed.add_field(name="Channel", value=invite.channel.mention, inline=True)
        embed.add_field(name="Uses", value=invite.max_uses or "Unlimited", inline=True)
        embed.add_field(name="Expires In", value=invite.max_age or "Never", inline=True)
        embed.add_field(name="Created By", value=invite.inviter.mention if invite.inviter else "Unknown", inline=False)

        embed.set_footer(text=f"Guild ID: {guild.id}")
        await self.send_log(guild, "invites", embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        guild = invite.guild
        embed = discord.Embed(
            title="❌ Invite Deleted",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Code", value=invite.code, inline=True)
        embed.add_field(name="Channel", value=invite.channel.mention if invite.channel else "Unknown", inline=True)

        embed.set_footer(text=f"Guild ID: {guild.id}")
        await self.send_log(guild, "invites", embed)


    # ----------------------
    # Webhook Events
    # ----------------------
    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        embed = discord.Embed(
            title="🪝 Webhooks Updated",
            description=f"Webhooks were updated in {channel.mention}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.set_footer(text=f"Guild ID: {guild.id}")
        await self.send_log(guild, "webhooks", embed)


    # ----------------------
    # Scheduled Events
    # ----------------------
    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent):
        embed = discord.Embed(
            title="📅 Scheduled Event Created",
            description=f"**{event.name}**",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Starts", value=event.start_time.strftime('%Y-%m-%d %H:%M UTC'))
        if event.end_time:
            embed.add_field(name="Ends", value=event.end_time.strftime('%Y-%m-%d %H:%M UTC'))
        if event.location:
            embed.add_field(name="Location", value=event.location, inline=False)
        embed.set_footer(text=f"Guild ID: {event.guild.id}")
        if event.cover_image:
            embed.set_image(url=event.cover_image.url)

        await self.send_log(event.guild, "events", embed)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        embed = discord.Embed(
            title="❌ Scheduled Event Deleted",
            description=f"**{event.name}**",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Guild ID: {event.guild.id}")
        await self.send_log(event.guild, "events", embed)

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.start_time != after.start_time:
            changes.append(f"**Start:** {before.start_time} → {after.start_time}")
        if before.end_time != after.end_time:
            changes.append(f"**End:** {before.end_time} → {after.end_time}")
        if before.location != after.location:
            changes.append(f"**Location:** {before.location} → {after.location}")
        if before.description != after.description:
            changes.append("**Description Updated**")

        if changes:
            embed = discord.Embed(
                title="♻️ Scheduled Event Updated",
                description="\n".join(changes),
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"Guild ID: {after.guild.id}")
            await self.send_log(after.guild, "events", embed)

    @commands.Cog.listener()
    async def on_scheduled_event_user_add(self, event: discord.ScheduledEvent, user: discord.User):
        embed = discord.Embed(
            title="👤 User Subscribed",
            description=f"{user.mention} subscribed to **{event.name}**",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Guild ID: {event.guild.id}")
        await self.send_log(event.guild, "events", embed)

    @commands.Cog.listener()
    async def on_scheduled_event_user_remove(self, event: discord.ScheduledEvent, user: discord.User):
        embed = discord.Embed(
            title="👤 User Unsubscribed",
            description=f"{user.mention} unsubscribed from **{event.name}**",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Guild ID: {event.guild.id}")
        await self.send_log(event.guild, "events", embed)



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