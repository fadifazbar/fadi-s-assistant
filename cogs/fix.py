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

        mode = mode.lower()
        if mode not in ["simple", "advanced"]:
            return await ctx.send("❌ Invalid mode. Use `$fix simple` or `$fix advanced`.")

        # === Confirmation Step ===
        confirm_msg = await ctx.send(
            f"⚠️ Are you sure you want to reset the server with **{mode.capitalize()}** mode?\n"
            "This will delete channels and roles (except this channel, stickers, emojis, and protected roles)."
            "\n\nReply with `yes` to confirm, or anything else to cancel."
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=30.0)
        except Exception:
            return await ctx.send("❌ Confirmation timed out. Cancelled.")

        if reply.content.lower() != "yes":
            return await ctx.send("❌ Cancelled.")

        # Try DMing the owner
        try:
            await ctx.author.send(f"🔧 Fixing the server **{ctx.guild.name}** in `{mode}` mode...")
        except discord.Forbidden:
            pass

        guild = ctx.guild

        # === DELETE CHANNELS ===
        for channel in guild.channels:
            if channel.id == ctx.channel.id:
                continue
            try:
                await channel.delete()
            except (discord.Forbidden, discord.HTTPException):
                continue

        # === DELETE ROLES ===
        for role in guild.roles:
            if role.is_default() or role >= guild.me.top_role:
                continue
            try:
                await role.delete()
            except (discord.Forbidden, discord.HTTPException):
                continue

        # === SIMPLE MODE ===
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

        # === ADVANCED MODE ===
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
                   "「📜」staff rules" , "「💬」staff chat", "「🔨」staff discussion", "「👾」staff cmds"

                ],
            }
            roles = [
                # === Ownership / High Staff ===
                ("👑〉Owner", discord.Permissions.all(), 0xFFF700),
                ("🤴〉Co-Owner", discord.Permissions.all(), 0x09FF00),
                ("💼〉Community Manager", discord.Permissions(manage_guild=True, manage_messages=True, manage_roles=True, view_audit_log=True), 0x00AAFF),
                ("⚒️〉Manager", discord.Permissions(manage_channels=True, manage_messages=True, manage_roles=True, mute_members=True, move_members=True), 0xFF8000),
                ("🛠️〉Administrator", discord.Permissions(administrator=True), 0xFF1100),

                # === Moderation ===
                ("🔨〉Moderator", discord.Permissions(kick_members=True, ban_members=True, manage_messages=True, mute_members=True, move_members=True), 0xA600FF),
                ("🔓〉Trial Moderator", discord.Permissions(manage_messages=True, mute_members=True), 0xFFDD00),
                ("🕵️〉Security", discord.Permissions(ban_members=True, kick_members=True, view_audit_log=True), 0x2c3e50),
                ("📞〉Support Team", discord.Permissions(manage_messages=True, read_message_history=True), 0x66FF99),
                ("🛎️〉Helper", discord.Permissions(manage_messages=True, read_message_history=True), 0x16a085),

                # === Utility / Team Roles ===
                ("🎨〉Designer", discord.Permissions(manage_emojis_and_stickers=True, attach_files=True, embed_links=True), 0xFF66CC),
                ("🎉〉Event Manager", discord.Permissions(manage_events=True, mention_everyone=True, move_members=True), 0x00E5FF),
                ("📦〉Giveaway Manager", discord.Permissions(manage_messages=True, mention_everyone=True), 0xf39c12),
                ("👨‍💻〉Developer", discord.Permissions(manage_guild=True, manage_roles=True, manage_channels=True, manage_messages=True), 0x4287f5),

                # === Bots ===
                ("👾〉Bots", discord.Permissions.all(), 0xFF00F7),
                

                # === Community Roles ===
                ("🌟〉Vip", discord.Permissions(read_messages=True, send_messages=True, use_external_emojis=True, connect=True, speak=True), 0xF3FC74),
                ("🎮〉Gamer", discord.Permissions(send_messages=True, connect=True, speak=True, use_application_commands=True), 0x00FF9C),
                ("🤗〉Members", discord.Permissions(read_messages=True, send_messages=True, connect=True, speak=True), 0x81DEBF),
                
                # === Ping Roles ===
                ("📢〉Announcement Ping", discord.Permissions.none(), 0xFC8674),
                ("‼️〉Important Ping", discord.Permissions.none(), 0x7496FC),
                ("🔋〉Chat Revive Ping", discord.Permissions.none(), 0x74FC7D),
            ]

        # === CREATE CATEGORIES + CHANNELS ===
async def create_channels(guild, categories):
    created_channels = {}
    for cat_name, chans in categories.items():
        try:
            # Decide if category should be hidden (staff-only)
            staff_only = any(word in cat_name.lower() for word in ["staff", "admin", "🔒"])

            overwrites = None
            if staff_only:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False)
                }
                # Allow staff roles
                staff_roles = [
                    "🛠️〉Administrator", "⚒️〉Manager", "💼〉Community Manager", "🔨〉Moderator",
                    "🔓〉Trial Moderator", "🕵️〉Security", "📞〉Support Team", "🛎️〉Helper",
                    "🎉〉Event Manager", "📦〉Giveaway Manager"
                ]
                for role_name in staff_roles:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            # Create category with overwrites (hidden if staff-only)
            category = await guild.create_category(cat_name, overwrites=overwrites)
        except Exception:
            continue

        for chan in chans:
            try:
                # Create voice or text channel
                if "voice" in cat_name.lower() or "🔊" in cat_name:
                    ch = await guild.create_voice_channel(chan, category=category)
                else:
                    ch = await guild.create_text_channel(chan, category=category)

                created_channels[chan] = ch
            except Exception:
                continue

    return created_channels

        # === CREATE ROLES (with permissions + hoist) ===
        new_roles = []
        if mode == "simple":
            for rname, perms in roles:
                try:
                    role = await guild.create_role(name=rname, permissions=perms, hoist=True)
                    new_roles.append(role)
                except Exception:
                    continue
        else:
            for rname, perms, color in roles:
                try:
                    role = await guild.create_role(name=rname, permissions=perms, hoist=True, color=discord.Color(color))
                    new_roles.append(role)
                except Exception:
                    continue
            # Reorder roles
            try:
                positions = {role: (len(new_roles) - i) for i, role in enumerate(new_roles)}
                await guild.edit_role_positions(positions=positions)
            except Exception:
                pass

            # === Set AFK & Boost Channel ===
            afk_channel = created_channels.get("「😴」Afk")
            boost_channel = created_channels.get("「🚀」boosts")
            try:
                await guild.edit(
                    afk_channel=afk_channel,
                    system_channel=boost_channel,
                    system_channel_flags=discord.SystemChannelFlags(
                        join_notifications=False,
                        premium_subscriptions=True,  # only boosts
                        guild_reminder_notifications=False,
                        join_notification_replies=False
                    )
                )
            except Exception:
                pass

        await ctx.send(f"✅ Successfully reset the server with **{mode.capitalize()}** mode!")

async def setup(bot):
    await bot.add_cog(FixServer(bot))
