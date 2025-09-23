# cogs/logging.py
import discord
from discord.ext import commands
from discord import app_commands, ui
import os, json, difflib
from datetime import datetime  # fixed typo

Embed_Colors = {
    "red": discord.Color(0xFF0000),
    "orange": discord.Color(0xFF6A00),
    "yellow": discord.Color(0xFFEA00),
    "green": discord.Color(0x2FFF00),
    "darkgreen": discord.Color(0x126300),
    "cyan": discord.Color(0x00F2FF),
    "blue": discord.Color(0x009DFF),
    "darkblue": discord.Color(0x1100FF),
    "purple": discord.Color(0x9900FF),
    "pink": discord.Color(0xFF00A6)
}


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

    # ---------------------
    # Logs Events
    # ----------------------


    # ----------------------
    # Message Events
    # ----------------------
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=Embed_Colors["red"],
            timestamp=datetime.utcnow()
        )

        # --- Most important info first ---
        embed.add_field(name="👤 Author", value=f"{message.author.mention} ({message.author})", inline=False)

        # Content with pinned indicator
        content = message.content or "*No content*"
        if message.pinned:
            content += " 📌"
        embed.add_field(name="💬 Content", value=content[:1024], inline=False)

        # Reply info (if applicable)
        if message.reference and (ref := message.reference.resolved):
            embed.add_field(
                name="↩️ Replying To",
                value=f"{ref.author.mention} ({ref.author})\n[Jump to Original]({ref.jump_url})",
                inline=False
            )

        # Attachments
        if message.attachments:
            files = [f"[{a.filename}]({a.url})" for a in message.attachments]
            embed.add_field(name="📎 Attachments", value="\n".join(files), inline=False)

            # Show first image if present
            first_img = next(
                (a.url for a in message.attachments if a.content_type and a.content_type.startswith("image/")), None
            )
            if first_img:
                embed.set_image(url=first_img)

        # Channel info with ID
        embed.add_field(
            name="📍 Channel",
            value=f"{message.channel.mention} ({message.channel.id})",
            inline=False
        )

        # Author ID only
        embed.add_field(name="🆔 Author ID", value=message.author.id, inline=True)

        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Guild ID: {message.guild.id}")

        await self.send_log(message.guild, "messages", embed)


    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return

        now = datetime.utcnow()

        # --- Case 1: Pin/Unpin event only ---
        if before.content == after.content and before.pinned != after.pinned:
            if after.pinned:
                title = "📌 Message Pinned"
                color = Embed_Colors["yellow"]
            else:
                title = "📌 Message Unpinned"
                color = Embed_Colors["darkgreen"]

            embed = discord.Embed(
                title=title,
                color=color,
                timestamp=now
            )
            embed.add_field(name="👤 Author", value=f"{before.author.mention} ({before.author})", inline=False)

            msg_link = f"[Jump to Message]({after.jump_url})"
            embed.add_field(
                name="📍 Channel",
                value=f"{before.channel.mention} ({before.channel.id})\n{msg_link}",
                inline=False
            )

            embed.add_field(name="💬 Content", value=(before.content or "*Empty*")[:1024], inline=False)

            embed.set_thumbnail(url=before.author.display_avatar.url)
            embed.set_footer(text=f"Guild ID: {before.guild.id}")
            return await self.send_log(before.guild, "messages", embed)

        # --- Case 2: Normal content edit ---
        if before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=Embed_Colors["orange"],
            timestamp=now
        )

        # Author info
        embed.add_field(name="👤 Author", value=f"{before.author.mention} ({before.author})", inline=False)

        # Channel + Jump Link
        msg_link = f"[Jump to Message]({after.jump_url})"
        embed.add_field(
            name="📍 Channel",
            value=f"{before.channel.mention} ({before.channel.id})\n{msg_link}",
            inline=False
        )

        # Before/After content
        embed.add_field(name="📝 Before", value=(before.content or "*Empty*")[:1024], inline=False)
        embed.add_field(name="📝 After", value=(after.content or "*Empty*")[:1024], inline=False)

        # Reply info (if applicable)
        if after.reference and (ref := after.reference.resolved):
            embed.add_field(
                name="↩️ Replying To",
                value=f"{ref.author.mention} ({ref.author})\n[Jump to Original]({ref.jump_url})",
                inline=False
            )

        # Attachments (after edit)
        if after.attachments:
            files = [f"[{a.filename}]({a.url})" for a in after.attachments]
            embed.add_field(name="📎 Attachments", value="\n".join(files), inline=False)

            first_img = next(
                (a.url for a in after.attachments if a.content_type and a.content_type.startswith("image/")), None
            )
            if first_img:
                embed.set_image(url=first_img)

        embed.add_field(name="🆔 Author ID", value=before.author.id, inline=True)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        embed.set_footer(text=f"Guild ID: {before.guild.id}")

        await self.send_log(before.guild, "messages", embed)




    # ----------------------
    # Member Events
    # ----------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Ignore bots
        if member.bot:
            return

        now = datetime.utcnow()
        account_age = now - member.created_at

        # Break down account age into Y/D/H/M/S
        years, remainder = divmod(account_age.total_seconds(), 31536000)
        days, remainder = divmod(remainder, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        # Build account age string (skip zeros)
        account_parts = []
        if years: account_parts.append(f"{int(years)} Year(s)")
        if days: account_parts.append(f"{int(days)} Day(s)")
        if hours: account_parts.append(f"{int(hours)} Hour(s)")
        if minutes: account_parts.append(f"{int(minutes)} Minute(s)")
        if seconds: account_parts.append(f"{int(seconds)} Second(s)")
        account_age_str = ", ".join(account_parts) + " Ago"

        # Member join position among real humans
        human_members = [m for m in member.guild.members if not m.bot]
        join_pos = sorted(human_members, key=lambda m: m.joined_at or now).index(member) + 1

        # Build embed
        embed = discord.Embed(
            title="👤 Member Joined",
            description=f"{member.mention} ({member} / {member.id})",
            color=Embed_Colors["green"],
            timestamp=now
        )

        embed.add_field(name="📆 Account Age", value=f"Created {account_age_str}", inline=False)
        embed.add_field(name="🔢 Member #", value=f"#{join_pos:,}", inline=True)

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Guild ID: {member.guild.id}")

        await self.send_log(member.guild, "members", embed)



    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # Ignore bots
        if member.bot:
            return

        now = datetime.utcnow()

        # Member position among real humans
        human_members = [m for m in member.guild.members if not m.bot]
        join_position = sorted(human_members, key=lambda m: m.joined_at or now).index(member) + 1

        # Account age
        account_age = now - member.created_at
        years, remainder = divmod(account_age.total_seconds(), 31536000)
        days, remainder = divmod(remainder, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        account_parts = []
        if years: account_parts.append(f"{int(years)} Year(s)")
        if days: account_parts.append(f"{int(days)} Day(s)")
        if hours: account_parts.append(f"{int(hours)} Hour(s)")
        if minutes: account_parts.append(f"{int(minutes)} Minute(s)")
        if seconds: account_parts.append(f"{int(seconds)} Second(s)")
        account_age_str = ", ".join(account_parts) + " Ago"

        # Time spent in guild
        if member.joined_at:
            time_in_guild = now - member.joined_at
            guild_days = time_in_guild.days
            guild_hours, remainder = divmod(time_in_guild.seconds, 3600)
            guild_minutes, guild_seconds = divmod(remainder, 60)

            guild_parts = []
            if guild_days: guild_parts.append(f"{guild_days} Day(s)")
            if guild_hours: guild_parts.append(f"{guild_hours} Hour(s)")
            if guild_minutes: guild_parts.append(f"{guild_minutes} Minute(s)")
            if guild_seconds: guild_parts.append(f"{guild_seconds} Second(s)")
            guild_time_str = ", ".join(guild_parts)
        else:
            guild_time_str = "Unknown"

        # Roles
        roles = [role.mention for role in member.roles if role != member.guild.default_role]
        roles_str = ", ".join(roles) if roles else "None"

        # Build embed
        embed = discord.Embed(
            title="👤 Member Left",
            description=f"{member.mention} ({member} / {member.id})",
            color=Embed_Colors["red"],
            timestamp=now
        )

        # Add fields top-to-bottom
        embed.add_field(name="🔢 Member #", value=f"#{join_position:,}", inline=True)
        embed.add_field(name="📆 Account Age", value=f"Created {account_age_str}", inline=False)
        embed.add_field(name="⏳ Time in Guild", value=guild_time_str, inline=False)
        embed.add_field(name="🎭 Roles", value=roles_str[:1024], inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Guild ID: {member.guild.id}")

        await self.send_log(member.guild, "members", embed)



    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Ignore bots
        if before.bot or after.bot:
            return

        now = datetime.utcnow()

        # --- 1. Nickname changes ---
        if before.nick != after.nick:
            responsible = None
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                    if entry.target.id == after.id and entry.before.nick != entry.after.nick:
                        responsible = entry.user
                        break
            except Exception:
                pass

            embed = discord.Embed(
                title="📝 Nickname Changed",
                color=Embed_Colors["blue"],
                timestamp=now
            )
            embed.add_field(name="👤 Member", value=after.mention, inline=False)
            embed.add_field(name="📝 Before", value=before.nick or "*None*", inline=True)
            embed.add_field(name="📝 After", value=after.nick or "*None*", inline=True)
            if responsible:
                embed.add_field(name="🥀 Changed By", value=responsible.mention, inline=False)

            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"🆔 User ID: {after.id} | Guild ID: {after.guild.id}")
            await self.send_log(after.guild, "members", embed)

        # --- 2. Timeouts ---
        if before.communication_disabled_until != after.communication_disabled_until:
            responsible = None
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                    if entry.target.id == after.id and entry.before.communication_disabled_until != entry.after.communication_disabled_until:
                        responsible = entry.user
                        break
            except Exception:
                pass

            embed = discord.Embed(
                title="⏱️ Timeout Updated",
                color=Embed_Colors["cyan"],
                timestamp=now
            )
            embed.add_field(name="👤 Member", value=after.mention, inline=False)
            embed.add_field(
                name="⏱️ Timeout Until",
                value=str(after.communication_disabled_until) if after.communication_disabled_until else "None",
                inline=False
            )
            if responsible:
                embed.add_field(name="🥀 Updated By", value=responsible.mention, inline=False)

            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"🆔 User ID: {after.id} | Guild ID: {after.guild.id}")
            await self.send_log(after.guild, "members", embed)

        # --- 3. Role changes ---
        if before.roles != after.roles:
            before_roles = set(before.roles)
            after_roles = set(after.roles)

            added_roles = after_roles - before_roles
            removed_roles = before_roles - after_roles

            responsible = None
            try:
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                    if entry.target.id == after.id:
                        responsible = entry.user
                        break
            except Exception:
                pass

            embed = discord.Embed(
                title="🎭 Roles Updated",
                color=Embed_Colors["purple"],
                timestamp=now
            )
            embed.add_field(name="👤 Member", value=after.mention, inline=False)
            if added_roles:
                embed.add_field(
                    name="🟢 Roles Added",
                    value=", ".join(r.mention for r in added_roles),
                    inline=False
                )
            if removed_roles:
                embed.add_field(
                    name="🔴 Roles Removed",
                    value=", ".join(r.mention for r in removed_roles),
                    inline=False
                )
            if responsible:
                embed.add_field(name="🥀 Updated By", value=responsible.mention, inline=False)

            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text=f"🆔 User ID: {after.id} | Guild ID: {after.guild.id}")
            await self.send_log(after.guild, "members", embed)



    # ----------------------
    # Role Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        guild = role.guild
        moderator = "Unknown"
        moderator_avatar = None
        created_by_bot = False

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    moderator = entry.user.mention
                    moderator_avatar = entry.user.display_avatar.url
                    created_by_bot = entry.user.bot  # True if bot created the role
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="🎭 Role Created",
            description=f"{role.mention} ({role.id})",
            color=Embed_Colors["green"],
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="👤 Moderator", value=moderator, inline=True)
        embed.add_field(name="🆔 Role ID", value=role.id, inline=True)
        embed.add_field(name="🤖 Created By Bot", value=str(created_by_bot), inline=True)
        embed.add_field(name="📌 Position", value=role.position, inline=True)
        embed.add_field(name="🎨 Color", value=str(role.color), inline=True)

        # Use moderator avatar as thumbnail if available
        if moderator_avatar:
            embed.set_thumbnail(url=moderator_avatar)

        embed.set_footer(text=f"🛡️ Guild ID: {guild.id}")

        await self.send_log(guild, "roles", embed)


    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        moderator = "Unknown"
        moderator_avatar = None
        deleted_by_bot = False

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    moderator = entry.user.mention
                    moderator_avatar = entry.user.display_avatar.url
                    deleted_by_bot = entry.user.bot
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="❌ Role Deleted",
            description=f"{role.name} ({role.id}",
            color=Embed_Colors["red"],
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="👤 Moderator", value=moderator, inline=True)
        embed.add_field(name="🆔 Role ID", value=role.id, inline=True)
        embed.add_field(name="🤖 Deleted By Bot", value=str(deleted_by_bot), inline=True)
        embed.add_field(name="📌 Position", value=role.position, inline=True)
        embed.add_field(name="🎨 Color", value=str(role.color), inline=True)

        if moderator_avatar:
            embed.set_thumbnail(url=moderator_avatar)

        embed.set_footer(text=f"🛡️ Guild ID: {guild.id}")

        await self.send_log(guild, "roles", embed)


    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        guild = after.guild
        moderator = "Unknown"
        moderator_avatar = None

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
                if entry.target.id == after.id:
                    moderator = entry.user.mention
                    moderator_avatar = entry.user.display_avatar.url
                    break
        except discord.Forbidden:
            pass

        changes = False
        embed = discord.Embed(
            title="🎭 Role Updated",
            color=Embed_Colors["orange"],
            timestamp=datetime.utcnow()
        )

        # Moderator
        embed.add_field(name="👤 Moderator", value=moderator, inline=False)
        if moderator_avatar:
            embed.set_thumbnail(url=moderator_avatar)

        # Name change
        if before.name != after.name:
            embed.add_field(name="📝 Name Change", value=f"{before.name} → {after.name}", inline=False)
            changes = True

        # Color change
        if before.color != after.color:
            embed.add_field(name="🎨 Color Update", value=f"{before.color} → {after.color}", inline=False)
            changes = True

        # Permissions change
        if before.permissions != after.permissions:
            embed.add_field(name="⚙️ Permissions Updated", value="Yes", inline=False)
            changes = True

        # Position change
        if before.position != after.position:
            embed.add_field(name="📌 Position Change", value=f"{before.position} → {after.position}", inline=False)
            changes = True

        # Role ID
        embed.add_field(name="🆔 Role ID", value=after.id, inline=True)

        if changes:
            await self.send_log(guild, "roles", embed)



    # ----------------------
    # Emoji & Sticker Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]):
        now = datetime.utcnow()
        added = [e for e in after if e.id not in [b.id for b in before]]
        removed = [e for e in before if e.id not in [a.id for a in after]]
        renamed = [a for a in after for b in before if a.id == b.id and a.name != b.name]

        if not (added or removed or renamed):
            return

        embed = discord.Embed(
            title="😃 Emojis Updated",
            color=Embed_Colors["purple"],
            timestamp=now
        )

        # Moderator from audit logs
        moderator = "Unknown"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.emoji_update):
                if added and any(e.id == entry.target.id for e in added):
                    moderator = entry.user
                    break
                if renamed and any(e.id == entry.target.id for e in renamed):
                    moderator = entry.user
                    break
        except discord.Forbidden:
            pass

        # Added emojis
        for e in added:
            anim = "🌀" if e.animated else "⚪"
            embed.add_field(
                name=f"🟢 Added {anim}",
                value=f"Name: {e.name}\nID: {e.id}",
                inline=False
            )
            embed.set_thumbnail(url=e.url)

        # Removed emojis
        for e in removed:
            anim = "🌀" if e.animated else "⚪"
            embed.add_field(
                name=f"🔴 Removed {anim}",
                value=f"📛 Name: {e.name}\n🆔 ID: {e.id}",
                inline=False
            )
            embed.set_thumbnail(url=e.url)

        # Renamed emojis
        for a in renamed:
            b = next((x for x in before if x.id == a.id), None)
            if not b:
                continue
            anim = "🌀" if a.animated else "⚪"
            embed.add_field(
                name=f"🔄 Renamed {anim}",
                value=f"📛 {b.name} → {a.name}\n🆔 ID: {a.id}",
                inline=False
            )
            embed.set_thumbnail(url=a.url)

        embed.add_field(name="🥀 Moderator", value=moderator.mention if isinstance(moderator, discord.Member) else moderator, inline=False)
        embed.set_footer(text=f"Guild ID: {guild.id}")

        # Send embed to logging channel
        log_message = await self.send_log(guild, "emojis", embed)

        # React with the actual added or renamed emojis
        for e in added + renamed:
            try:
                await log_message.add_reaction(e)
            except Exception:
                continue


    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before: list[discord.Sticker], after: list[discord.Sticker]):
        now = datetime.utcnow()
        added = [s for s in after if s.id not in [b.id for b in before]]
        removed = [s for s in before if s.id not in [a.id for a in after]]
        renamed = [a for a in after for b in before if a.id == b.id and a.name != b.name]

        if not (added or removed or renamed):
            return

        embed = discord.Embed(
            title="🎟️ Stickers Updated",
            color=Embed_Colors["purple"],
            timestamp=now
        )

        # Moderator from audit logs
        moderator = "Unknown"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.sticker_update):
                if added and any(s.id == entry.target.id for s in added):
                    moderator = entry.user
                    break
                if renamed and any(s.id == entry.target.id for s in renamed):
                    moderator = entry.user
                    break
        except discord.Forbidden:
            pass

        # Added stickers
        for s in added:
            embed.add_field(
                name=f"🟢 Added",
                value=f"📛 Name: {s.name}\nID: {s.id}\n⚙ Type: {s.format}",
                inline=False
            )
            if s.url:
                embed.set_thumbnail(url=s.url)

        # Removed stickers
        for s in removed:
            embed.add_field(
                name=f"🔴 Removed",
                value=f"📛 Name: {s.name}\nID: {s.id}\n⚙ Type: {s.format}",
                inline=False
            )
            if s.url:
                embed.set_thumbnail(url=s.url)

        # Renamed stickers
        for a in renamed:
            b = next((x for x in before if x.id == a.id), None)
            if not b:
                continue
            embed.add_field(
                name=f"🔄 Renamed",
                value=f"📛 {b.name} → {a.name}\nID: {a.id}\n⚙ Type: {a.format}",
                inline=False
            )
            if a.url:
                embed.set_thumbnail(url=a.url)

        embed.add_field(
            name="🥀 Moderator",
            value=moderator.mention if isinstance(moderator, discord.Member) else moderator,
            inline=False
        )
        embed.set_footer(text=f"Guild ID: {guild.id}")

        await self.send_log(guild, "stickers", embed)
        



    # ----------------------
    # Thread Events
    # ----------------------
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        now = datetime.utcnow()

        # Determine thread type with emoji
        thread_type_map = {
            discord.ChannelType.public_thread: "💬 Public",
            discord.ChannelType.private_thread: "🔒 Private",
            discord.ChannelType.news_thread: "📢 Announcement"
        }
        thread_type = thread_type_map.get(thread.type, str(thread.type))

        embed = discord.Embed(
            title="🧵🟢 Thread Created",
            description=f"📛 {thread.name} ({thread.id})",
            color=Embed_Colors["green"],
            timestamp=now
        )

        # Core info with emojis
        embed.add_field(name="👤 Owner", value=f"{thread.owner.mention if thread.owner else thread.owner_id}", inline=True)
        embed.add_field(name="📂 Parent Channel", value=f"{thread.parent.name} ({thread.parent.id})", inline=True)
        embed.add_field(name="📌 Thread Type", value=thread_type, inline=True)
        embed.add_field(name="⏱️ Auto-Archive Duration", value=f"{thread.auto_archive_duration} minutes", inline=True)
        embed.add_field(name="🔒 Locked", value=str(thread.locked), inline=True)
        embed.add_field(name="👥 Member Count", value=str(thread.member_count), inline=True)

        # Use owner's avatar as thumbnail
        if thread.owner:
            embed.set_thumbnail(url=thread.owner.display_avatar.url)
        else:
            embed.set_thumbnail(url=discord.Embed.Empty)

        embed.set_footer(text=f"Guild ID: {thread.guild.id}")

        await self.send_log(thread.guild, "threads", embed)


    
    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        now = datetime.utcnow()
        guild = thread.guild
        moderator = "Unknown"

        # Try to get responsible user from audit logs
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.thread_delete):
                if entry.target.id == thread.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            moderator = "Unknown"

        # Determine thread type with emoji
        thread_type_map = {
            discord.ChannelType.public_thread: "💬 Public",
            discord.ChannelType.private_thread: "🔒 Private",
            discord.ChannelType.news_thread: "📢 Announcement"
        }
        thread_type = thread_type_map.get(thread.type, str(thread.type))

        embed = discord.Embed(
            title="🧵🔴 Thread Deleted",
            description=f"📛 {thread.name} ({thread.id})",
            color=Embed_Colors["red"],
            timestamp=now
        )

        # Core info with emojis
        embed.add_field(name="👤 Owner", value=f"{thread.owner.mention if thread.owner else thread.owner_id}", inline=True)
        embed.add_field(name="📂 Parent Channel", value=f"{thread.parent.name} ({thread.parent.id})", inline=True)
        embed.add_field(name="📌 Thread Type", value=thread_type, inline=True)
        embed.add_field(name="⏱️ Auto-Archive Duration", value=f"{thread.auto_archive_duration} minutes", inline=True)
        embed.add_field(name="🔒 Locked", value=str(thread.locked), inline=True)
        embed.add_field(name="👥 Member Count", value=str(thread.member_count), inline=True)

        # Responsible user
        if moderator != "Unknown":
            embed.add_field(name="🥀 Responsible User", value=moderator.mention, inline=False)
            embed.set_thumbnail(url=moderator.display_avatar.url)
        else:
            embed.set_thumbnail(url=discord.Embed.Empty)

        embed.set_footer(text=f"Guild ID: {thread.guild.id}")

        await self.send_log(thread.guild, "threads", embed)


    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        now = datetime.utcnow()
        changes = []

        # Track changes
        if before.name != after.name:
            changes.append(f"✏️ **Name:** {before.name} → {after.name}")
        if before.archived != after.archived:
            changes.append(f"📦 **Archived:** {before.archived} → {after.archived}")
        if before.locked != after.locked:
            changes.append(f"🔒 **Locked:** {before.locked} → {after.locked}")
        if before.auto_archive_duration != after.auto_archive_duration:
            changes.append(f"⏱️ **Auto-Archive Duration:** {before.auto_archive_duration} → {after.auto_archive_duration} minutes")
        if before.member_count != after.member_count:
            changes.append(f"👥 **Member Count:** {before.member_count} → {after.member_count}")

        if not changes:
            return

        # Determine thread type with emoji
        thread_type_map = {
            discord.ChannelType.public_thread: "💬 Public",
            discord.ChannelType.private_thread: "🔒 Private",
            discord.ChannelType.news_thread: "📢 Announcement"
        }
        thread_type = thread_type_map.get(after.type, str(after.type))

        # Get responsible user from audit logs
        responsible = None
        try:
            async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.thread_update):
                if entry.target.id == after.id:
                    responsible = entry.user
                    break
        except discord.Forbidden:
            pass

        # Create embed
        embed = discord.Embed(
            title="🧵 Thread Updated",
            description="\n".join(changes),
            color=Embed_Colors.get("orange", discord.Color.orange()),
            timestamp=now
        )

        embed.add_field(name="📛 Thread", value=f"{after.name} ({after.id})", inline=False)
        embed.add_field(name="👤 Owner", value=f"{after.owner.mention if after.owner else after.owner_id}", inline=True)
        embed.add_field(name="📂 Parent Channel", value=f"{after.parent.name} ({after.parent.id})", inline=True)
        embed.add_field(name="📌 Thread Type", value=thread_type, inline=True)

        if responsible:
            embed.add_field(name="🥀 Responsible User", value=responsible.mention, inline=False)
            embed.set_thumbnail(url=responsible.display_avatar.url)
        elif after.owner:
            embed.set_thumbnail(url=after.owner.display_avatar.url)
        else:
            embed.set_thumbnail(url=discord.Embed.Empty)

        embed.set_footer(text=f"Guild ID: {after.guild.id}")

        await self.send_log(after.guild, "threads", embed)



    # ----------------------
    # Channel Events
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        now = datetime.utcnow()
        guild = channel.guild
        moderator = None

        # Determine responsible moderator from audit logs
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            pass

        # Map channel type to emojis
        channel_type_map = {
            discord.ChannelType.text: "💬 Text",
            discord.ChannelType.voice: "🔊 Voice",
            discord.ChannelType.category: "📂 Category",
            discord.ChannelType.news: "📢 Announcement",
            discord.ChannelType.stage_voice: "🎤 Stage"
        }
        channel_type_str = channel_type_map.get(channel.type, str(channel.type).capitalize())

        # Embed
        embed = discord.Embed(
            title="🟢 Channel Created",
            description=f"{channel.mention} ({channel.id})",
            color=Embed_Colors["green"],
            timestamp=now
        )

        # Fields
        embed.add_field(name="📝 Type", value=channel_type_str, inline=True)
        if isinstance(channel, discord.abc.GuildChannel) and getattr(channel, "category", None):
            embed.add_field(name="📂 Parent Category", value=f"{channel.category.name} ({channel.category.id})", inline=True)
        if moderator:
            embed.add_field(name="🥀 Created By", value=moderator.mention, inline=True)

        # Thumbnail
        if moderator:
            embed.set_thumbnail(url=moderator.display_avatar.url)
        else:
            embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)

        # Footer
        embed.set_footer(text=f"Channel ID: {channel.id} | Guild ID: {guild.id}")

        await self.send_log(guild, "channels", embed)


    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        now = datetime.utcnow()
        guild = channel.guild
        moderator = None

        # Determine responsible moderator from audit logs
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            pass

        # Map channel type to emojis
        channel_type_map = {
            discord.ChannelType.text: "💬 Text",
            discord.ChannelType.voice: "🔊 Voice",
            discord.ChannelType.category: "📂 Category",
            discord.ChannelType.news: "📢 Announcement",
            discord.ChannelType.stage_voice: "🎤 Stage"
        }
        channel_type_str = channel_type_map.get(channel.type, str(channel.type).capitalize())

        # Embed
        embed = discord.Embed(
            title="📢 Channel Deleted",
            description=f"{channel.name} ({channel.id})",
            color=Embed_Colors["red"],
            timestamp=now
        )

        # Fields
        embed.add_field(name="📝 Type", value=channel_type_str, inline=True)
        if isinstance(channel, discord.abc.GuildChannel) and getattr(channel, "category", None):
            embed.add_field(name="📂 Parent Category", value=f"{channel.category.name} ({channel.category.id})", inline=True)
        if moderator:
            embed.add_field(name="🥀 Deleted By", value=moderator.mention, inline=True)

        # Thumbnail
        if moderator:
            embed.set_thumbnail(url=moderator.display_avatar.url)
        else:
            embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)

        # Footer
        embed.set_footer(text=f"Channel ID: {channel.id} | Guild ID: {guild.id}")

        await self.send_log(guild, "channels", embed)


    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        guild = after.guild
        moderator = None

        # Get responsible mod
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id:
                    moderator = entry.user
                    break
        except discord.Forbidden:
            pass

        changes = []

        # Name change
        if before.name != after.name:
            changes.append(f"📛 **Name:** {before.name} → {after.name}")

        # Category / Parent change
        if before.category != after.category:
            old_cat = before.category.name if before.category else "None"
            new_cat = after.category.name if after.category else "None"
            changes.append(f"📂 **Category:** {old_cat} → {new_cat}")

        # NSFW status change
        if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
            changes.append(f"🔞 **NSFW:** {getattr(before, 'nsfw', False)} → {getattr(after, 'nsfw', False)}")

        # Slowmode / rate limit
        if getattr(before, "slowmode_delay", None) != getattr(after, "slowmode_delay", None):
            changes.append(f"🐢 **Slowmode:** {getattr(before, 'slowmode_delay', 0)}s → {getattr(after, 'slowmode_delay', 0)}s")

        # Topic change
        if getattr(before, "topic", None) != getattr(after, "topic", None):
            old_topic = getattr(before, "topic", "*None*") or "*None*"
            new_topic = getattr(after, "topic", "*None*") or "*None*"
            changes.append(f"💭 **Topic:** {old_topic[:256]} → {new_topic[:256]}")

        # Permissions change
        if getattr(before, "permissions", None) != getattr(after, "permissions", None):
            changes.append("🔒 **Permissions Updated**")

        if changes:
            embed = discord.Embed(
                title="📢 Channel Updated",
                description="\n".join(changes),
                color=Embed_Colors["orange"],
                timestamp=datetime.utcnow()
            )

            embed.add_field(name="💬 Channel", value=f"{after.mention} ({after.name} / {after.id})", inline=False)
            embed.add_field(name="🥀 Moderator", value=moderator.mention if moderator else "Unknown", inline=False)

            # Use moderator avatar as thumbnail if available
            if moderator:
                embed.set_thumbnail(url=moderator.display_avatar.url)
            else:
                embed.set_thumbnail(url=discord.Embed.Empty)

            embed.set_footer(text=f"Guild ID: {guild.id}")
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

            # Check if the bot is Discord-verified
            verified_status = "✅ Verified Bot" if getattr(member, "public_flags", None) and member.public_flags.verified_bot else "❌ Not Verified"

            embed = discord.Embed(
                title="🤖 Bot Added",
                description=f"{member.mention} ({member.name}#{member.discriminator} / {member.id})",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="🥀 Added By", value=moderator, inline=True)
            embed.add_field(name="🚩 Verification", value=verified_status, inline=True)

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Guild ID: {guild.id}")

            await self.send_log(guild, "bots", embed)



    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            guild = member.guild
            moderator = "Unknown"

            try:
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_remove):
                    if entry.target.id == member.id:
                        moderator = entry.user
                        break
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                title="🤖 Bot Removed",
                description=f"{member.mention} ({member.name}#{member.discriminator} / {member.id})",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(name="🥀 Removed By", value=moderator.mention if moderator != "Unknown" else moderator, inline=True)
            embed.add_field(name="🚩 Verification", value="✅" if member.public_flags.verified_bot else "❌", inline=True)

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Guild ID: {guild.id}")

            await self.send_log(guild, "bots", embed)


    # ----------------------
    # Server (Guild) Updates
    # ----------------------
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        changes = []

        # Track only the requested changes
        if before.name != after.name:
            changes.append(f"🏷️ **Server Name:** {before.name} → {after.name}")
        if before.icon != after.icon:
            changes.append("🖼️ **Server Icon Changed**")
        if before.banner != after.banner:
            changes.append("🖼️ **Server Banner Changed**")

        if changes:
            # Responsible moderator from audit logs
            moderator = "Unknown"
            try:
                async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
                    moderator = entry.user
                    break
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                title="🏛️ Server Updated",
                description="\n".join(changes),
                color=Embed_Colors["green"],
                timestamp=datetime.utcnow()
            )

            embed.add_field(name="🆔 Server ID", value=after.id, inline=True)
            embed.add_field(name="🥀 Responsible Moderator", value=moderator.mention if moderator != "Unknown" else moderator, inline=True)

            # Thumbnail: server icon if exists
            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
            else:
                embed.set_thumbnail(url=discord.Embed.Empty)

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
                color=Embed_Colors["red"]
            elif before.channel is None:
                changes.append(f"✅ Joined {after.channel.mention}")
                color=Embed_Colors["green"]
            else:
                changes.append(f"🔀 Moved {before.channel.mention} → {after.channel.mention}")
                color=Embed_Colors["cyan"]
        else:
            color=Embed_Colors["purple"]

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
            embed.add_field(name="🥀 User", value=member.mention, inline=True)
            embed.add_field(name="🆔 User ID", value=member.id, inline=True)

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
            color=Embed_Colors["green"],
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🔗 Code", value=invite.code, inline=True)
        embed.add_field(name="💬 Channel", value=invite.channel.mention, inline=True)
        embed.add_field(name="👆 Uses", value=invite.max_uses or "Unlimited", inline=True)
        embed.add_field(name="💀 Expires In", value=invite.max_age or "Never", inline=True)
        embed.add_field(name="🥀 Created By", value=invite.inviter.mention if invite.inviter else "Unknown", inline=False)

        embed.set_footer(text=f"Guild ID: {guild.id}")
        await self.send_log(guild, "invites", embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        guild = invite.guild
        embed = discord.Embed(
            title="❌ Invite Deleted",
            color=Embed_Colors["red"],
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🔗 Code", value=invite.code, inline=True)
        embed.add_field(name="💬 Channel", value=invite.channel.mention if invite.channel else "Unknown", inline=True)

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
            color=Embed_Colors["yellow"],
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
        moderator = "Unknown"
        moderator_avatar = discord.Embed.Empty
        try:
            async for entry in event.guild.audit_logs(limit=1, action=discord.AuditLogAction.event_create):
                if entry.target.id == event.id:
                    moderator = entry.user.mention
                    moderator_avatar = entry.user.display_avatar.url
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="📅 Scheduled Event Created",
            description=f"📛 **{event.name}** ({event.id})",
            color=Embed_Colors["green"],
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🟢 Starts", value=event.start_time.strftime('%Y-%m-%d %H:%M UTC'))
        if event.end_time:
            embed.add_field(name="🔴 Ends", value=event.end_time.strftime('%Y-%m-%d %H:%M UTC'))
        if event.location:
            embed.add_field(name="🚀 Location", value=event.location, inline=False)
        embed.add_field(name="🥀 Responsible Moderator", value=moderator, inline=True)

        embed.set_thumbnail(url=moderator_avatar)
        embed.set_footer(text=f"Guild ID: {event.guild.id}")
        if event.cover_image:
            embed.set_image(url=event.cover_image.url)

        await self.send_log(event.guild, "events", embed)


    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        moderator = "Unknown"
        moderator_avatar = discord.Embed.Empty
        try:
            async for entry in event.guild.audit_logs(limit=1, action=discord.AuditLogAction.event_delete):
                if entry.target.id == event.id:
                    moderator = entry.user.mention
                    moderator_avatar = entry.user.display_avatar.url
                    break
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="❌ Scheduled Event Deleted",
            description=f"📛 **{event.name}** ({event.id})",
            color=Embed_Colors["red"],
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🥀 Responsible Moderator", value=moderator, inline=True)
        embed.set_thumbnail(url=moderator_avatar)
        embed.set_footer(text=f"Guild ID: {event.guild.id}")

        await self.send_log(event.guild, "events", embed)


    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        changes = []
        if before.name != after.name:
            changes.append(f"📛 **Name:** {before.name} → {after.name}")
        if before.start_time != after.start_time:
            changes.append(f"🟢 **Start:** {before.start_time} → {after.start_time}")
        if before.end_time != after.end_time:
            changes.append(f"🔴 **End:** {before.end_time} → {after.end_time}")
        if before.location != after.location:
            changes.append(f"💬 **Location:** {before.location} → {after.location}")
        if before.description != after.description:
            changes.append("📃 **Description Updated**")

        if changes:
            moderator = "Unknown"
            moderator_avatar = discord.Embed.Empty
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.event_update):
                    if entry.target.id == after.id:
                        moderator = entry.user.mention
                        moderator_avatar = entry.user.display_avatar.url
                        break
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                title="♻️ Scheduled Event Updated",
                description="\n".join(changes),
                color=Embed_Colors["orange"],
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="🥀 Responsible Moderator", value=moderator, inline=True)
            embed.set_thumbnail(url=moderator_avatar)
            embed.set_footer(text=f"Guild ID: {after.guild.id}")

            await self.send_log(after.guild, "events", embed)


    @commands.Cog.listener()
    async def on_scheduled_event_user_add(self, event: discord.ScheduledEvent, user: discord.User):
        embed = discord.Embed(
            title="👤 User Entered",
            description=f"😁 {user.mention} entered to **{event.name}** ({event.id})",
            color=Embed_Colors["pink"],
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Guild ID: {event.guild.id}")
        await self.send_log(event.guild, "events", embed)

    @commands.Cog.listener()
    async def on_scheduled_event_user_remove(self, event: discord.ScheduledEvent, user: discord.User):
        embed = discord.Embed(
            title="👤 User Unsubscribed",
            description=f"😭 {user.mention} unsubscribed from **{event.name}** ({event.id})",
            color=Embed_Colors["red"],
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
