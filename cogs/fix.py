import asyncio
import discord
from discord.ext import commands

class FixServer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="fix")
    @commands.guild_only()
    async def fix(self, ctx, mode: str):
        """Fix the server structure: $fix simple or $fix advanced"""
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ Only the server owner can use this command.")

        mode = mode.lower().strip()
        if mode not in ["simple", "advanced"]:
            return await ctx.send("❌ Invalid mode. Use `$fix simple` or `$fix advanced`.")

        await ctx.send(
            f"⚠️ Are you sure you want to reset the server with **{mode.capitalize()}** mode?\n"
            "This will delete channels and roles (except this channel, stickers, emojis, and protected roles).\n\n"
            "Reply with `yes` to confirm, or anything else to cancel."
        )

        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=30.0)
        except Exception:
            return await ctx.send("❌ Confirmation timed out. Cancelled.")

        if reply.content.lower().strip() != "yes":
            return await ctx.send("❌ Cancelled.")

        # DM the owner (best-effort)
        try:
            await ctx.author.send(f"🔧 Fixing the server **{ctx.guild.name}** in `{mode}` mode...")
        except discord.Forbidden:
            pass

        guild = ctx.guild

        # === DELETE CHANNELS ===
        await ctx.send("🧹 Deleting channels...")
        for channel in list(guild.channels):
            if channel.id == ctx.channel.id:
                continue
            try:
                await channel.delete(reason="FixServer reset")
                await asyncio.sleep(0.2)
            except Exception as e:
                await ctx.send(f"⚠️ Failed to delete channel {channel.name}: {e}")

        # === DELETE ROLES ===
        await ctx.send("🧹 Deleting roles...")
        for role in list(guild.roles):
            if role.is_default() or role >= guild.me.top_role:
                continue
            try:
                await role.delete(reason="FixServer reset")
                await asyncio.sleep(0.2)
            except Exception as e:
                await ctx.send(f"⚠️ Failed to delete role {role.name}: {e}")

        # === DEFINE CATEGORIES AND ROLES ===
        if mode == "simple":
            categories = {
                "Important": ["rules", "announcements", "welcome", "goodbye"],
                "Main": ["chat", "bot-cmds", "memes", "media"],
            }
            roles = [
                ("Owner", discord.Permissions.all()),
                ("Co-Owner", discord.Permissions.all()),
                ("Admin", discord.Permissions(administrator=True)),
                ("Moderator", discord.Permissions(manage_messages=True, kick_members=True, ban_members=True)),
                ("Trial Moderator", discord.Permissions(manage_messages=True)),
                ("Bots", discord.Permissions(send_messages=True, embed_links=True)),
                ("Member", discord.Permissions(send_messages=True, read_messages=True)),
            ]
        else:
            categories = {
                "☆࿐ཽ༵༆༒〘🚨〙Important༒༆࿐ཽ༵☆": [
                    "「📜」rules", "「📢」announcements", "「ℹ️」server info",
                    "「👋」welcome", "「👋」goodbye", "「🥳」giveaways",
                    "「🎭」reaction roles", "「✅」verification", "「🚀」boosts",
                    "「📊」polls"
                ],
                "☆࿐ཽ༵༆༒〘💬〙Main Area༒༆࿐ཽ༵☆": [
                    "「💬」chat", "「🤖」bot cmds", "「🤣」memes",
                    "「🎥」media", "「🎨」art", "「💡」suggestions"
                ],
                "☆࿐ཽ༵༆༒〘🔊〙Voice Chats༒༆࿐ཽ༵☆": [
                    "「🔊」General Chat", "「😴」Afk", "「🎵」Music",
                    "「🎮」Gaming", "「🔴」Streams"
                ],
                "☆࿐ཽ༵༆༒〘👑〙Staff Only༒༆࿐ཽ༵☆": [
                    "「📜」staff rules", "「💬」staff chat", "「🔨」staff discussion", "「👾」staff cmds"
                ],
            }
            roles = [
                # Ownership / High Staff
                ("👑〉Owner", discord.Permissions.all(), 0xFFF700),
                ("🤴〉Co-Owner", discord.Permissions.all(), 0x09FF00),
                ("💼〉Community Manager", discord.Permissions(manage_guild=True, manage_messages=True, manage_roles=True, view_audit_log=True), 0x00AAFF),
                ("⚒️〉Manager", discord.Permissions(manage_channels=True, manage_messages=True, manage_roles=True, mute_members=True, move_members=True), 0xFF8000),
                ("🛠️〉Administrator", discord.Permissions(administrator=True), 0xFF1100),

                # Moderation
                ("🔨〉Moderator", discord.Permissions(kick_members=True, ban_members=True, manage_messages=True, mute_members=True, move_members=True), 0xA600FF),
                ("🔓〉Trial Moderator", discord.Permissions(manage_messages=True, mute_members=True), 0xFFDD00),
                ("🕵️〉Security", discord.Permissions(ban_members=True, kick_members=True, view_audit_log=True), 0x2c3e50),
                ("📞〉Support Team", discord.Permissions(manage_messages=True, read_message_history=True), 0x66FF99),
                ("🛎️〉Helper", discord.Permissions(manage_messages=True, read_message_history=True), 0x16a085),

                # Utility / Team Roles
                ("🎨〉Designer", discord.Permissions(manage_emojis_and_stickers=True, attach_files=True, embed_links=True), 0xFF66CC),
                ("🎉〉Event Manager", discord.Permissions(manage_events=True, mention_everyone=True, move_members=True), 0x00E5FF),
                ("📦〉Giveaway Manager", discord.Permissions(manage_messages=True, mention_everyone=True), 0xf39c12),
                ("👨‍💻〉Developer", discord.Permissions(manage_guild=True, manage_roles=True, manage_channels=True, manage_messages=True), 0x4287f5),

                # Bots
                ("👾〉Bots", discord.Permissions.all(), 0xFF00F7),

                # Community Roles
                ("🌟〉Vip", discord.Permissions(read_messages=True, send_messages=True, use_external_emojis=True, connect=True, speak=True), 0xF3FC74),
                ("🎮〉Gamer", discord.Permissions(send_messages=True, connect=True, speak=True, use_application_commands=True), 0x00FF9C),
                ("🤗〉Members", discord.Permissions(read_messages=True, send_messages=True, connect=True, speak=True), 0x81DEBF),

                # Ping Roles
                ("📢〉Announcement Ping", discord.Permissions.none(), 0xFC8674),
                ("‼️〉Important Ping", discord.Permissions.none(), 0x7496FC),
                ("🔋〉Chat Revive Ping", discord.Permissions.none(), 0x74FC7D),
            ]

        # === CREATE ROLES FIRST ===
        await ctx.send("🧱 Creating roles...")
        role_lookup = {}
        new_roles = []

        if mode == "simple":
            for rname, perms in roles:
                try:
                    role = await guild.create_role(name=rname, permissions=perms, hoist=True, reason="FixServer create roles")
                    role_lookup[rname] = role
                    new_roles.append(role)
                    await asyncio.sleep(0.2)
                except Exception as e:
                    await ctx.send(f"⚠️ Failed to create role {rname}: {e}")
        else:
            for rname, perms, color in roles:
                try:
                    role = await guild.create_role(
                        name=rname, permissions=perms, hoist=True, color=discord.Color(color), reason="FixServer create roles"
                    )
                    role_lookup[rname] = role
                    new_roles.append(role)
                    await asyncio.sleep(0.2)
                except Exception as e:
                    await ctx.send(f"⚠️ Failed to create role {rname}: {e}")

            # Reorder roles (best-effort)
            try:
                positions = {role: (len(new_roles) - i) for i, role in enumerate(new_roles)}
                await guild.edit_role_positions(positions=positions)
            except Exception as e:
                await ctx.send(f"⚠️ Failed to reorder roles: {e}")

        # === CREATE CATEGORIES (no overwrites yet) ===
        await ctx.send("📁 Creating categories...")
        category_objs = {}
        for cat_name in categories.keys():
            try:
                cat = await guild.create_category(name=cat_name, reason="FixServer create category")
                category_objs[cat_name] = cat
                await asyncio.sleep(0.2)
            except Exception as e:
                await ctx.send(f"❌ Failed to create category {cat_name}: {e}")

        # === Apply staff-only permissions after category creation ===
        if mode == "advanced":
            staff_cat_name = "☆࿐ཽ༵༆༒〘👑〙Staff Only༒༆࿐ཽ༵☆"
            staff_cat = category_objs.get(staff_cat_name)
            if staff_cat:
                try:
                    # Hide from @everyone
                    await staff_cat.set_permissions(guild.default_role, view_channel=False)
                    staff_roles_names = [
                        "🛠️〉Administrator", "⚒️〉Manager", "💼〉Community Manager", "🔨〉Moderator",
                        "🔓〉Trial Moderator", "🕵️〉Security", "📞〉Support Team", "🛎️〉Helper",
                        "🎉〉Event Manager", "📦〉Giveaway Manager"
                    ]
                    for rname in staff_roles_names:
                        role = role_lookup.get(rname) or discord.utils.get(guild.roles, name=rname)
                        if role:
                            await staff_cat.set_permissions(role, view_channel=True, send_messages=True)
                    await asyncio.sleep(0.2)
                except Exception as e:
                    await ctx.send(f"⚠️ Failed to set staff category permissions: {e}")

        # === CREATE CHANNELS ===
        await ctx.send("🧩 Creating channels...")
        created_channels = {}
        for cat_name, chans in categories.items():
            cat = category_objs.get(cat_name)
            if not cat:
                await ctx.send(f"⚠️ Skipping channels for {cat_name} (category missing).")
                continue

            for chan_name in chans:
                try:
                    if ("voice" in cat_name.lower()) or ("🔊" in cat_name):
                        ch = await guild.create_voice_channel(name=chan_name, category=cat, reason="FixServer create voice channel")
                    else:
                        ch = await guild.create_text_channel(name=chan_name, category=cat, reason="FixServer create text channel")
                    created_channels[chan_name] = ch
                    await asyncio.sleep(0.2)
                except Exception as e:
                    await ctx.send(f"❌ Failed to create channel {chan_name} in {cat_name}: {e}")

        # === Set AFK & System channels (advanced) ===
        if mode == "advanced":
            afk_channel = created_channels.get("「😴」Afk")
            boost_channel = created_channels.get("「🚀」boosts")
            try:
                await guild.edit(
                    afk_channel=afk_channel,
                    system_channel=boost_channel,
                    system_channel_flags=discord.SystemChannelFlags(
                        join_notifications=False,
                        premium_subscriptions=True,
                        guild_reminder_notifications=False,
                        join_notification_replies=False
                    )
                )
            except Exception as e:
                await ctx.send(f"⚠️ Failed to set AFK/system channels: {e}")

        await ctx.send(f"✅ Done! Server reset in **{mode.capitalize()}** mode.")

async def setup(bot):
    await bot.add_cog(FixServer(bot))
        
