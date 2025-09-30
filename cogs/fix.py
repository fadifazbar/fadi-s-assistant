import discord
from discord.ext import commands
import asyncio

class ServerFix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="fix")
    async def fix_server(self, ctx, mode: str):
        """
        Fix the server layout.
        Usage: $fix simple OR $fix advanced
        """
        # Only allow the server owner
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ Only the **server owner** can use this command.")
            return

        if mode.lower() not in ["simple", "advanced"]:
            await ctx.send("❌ Invalid mode. Use `simple` or `advanced`.")
            return

        guild = ctx.guild

        await ctx.send(f"⚠️ This will **reset channels and roles**. Type `CONFIRM` within 20s to continue.")

        def check(m):
            return m.author == ctx.author and m.content == "CONFIRM"

        try:
            await self.bot.wait_for("message", check=check, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send("⏳ Cancelled.")
            return

        # ===========================
        # 1. Delete channels & roles
        # ===========================
        for channel in guild.channels:
            try:
                await channel.delete()
            except Exception:
                continue

        for role in guild.roles:
            try:
                if role.is_default():
                    continue
                await role.delete()
            except Exception:
                continue

        await ctx.send("🧹 Cleared channels and roles. Rebuilding...")

        # ===========================
        # 2. Build structures
        # ===========================
        if mode.lower() == "simple":
            categories = {
                "Important": ["rules", "announcments", "welcome", "goodbye"],
                "Main": ["chat", "bot-cmds", "memes", "media"]
            }

            roles = [
                ("Owner", None),
                ("Co-Owner", None),
                ("Admin", None),
                ("Moderator", None),
                ("Trial Moderator", None),
                ("Bots", None),
                ("Member", None),
                ("Colorless", None),
            ]

        else:  # advanced
            categories = {
                "☆࿐ཽ༵༆༒〘🚨〙Important༒༆࿐ཽ༵☆": [
                    "「📜」rules",
                    "「📢」announcements",
                    "「ℹ️」server info",
                    "「👋」welcome",
                    "「👋」goodbye",
                    "「🥳」giveaways",
                    "「🎭」reaction roles",
                    "「✅」verification",
                    "「🚀」boosts",
                    "「📊」polls",
                ],
                "☆࿐ཽ༵༆༒〘💬〙Main Area༒༆࿐ཽ༵☆": [
                    "「💬」chat",
                    "「🤖」bot cmds",
                    "「🤣」memes",
                    "「🎥」media",
                    "「🎨」art",
                    "「💡」suggestions",
                ],
                "☆࿐ཽ༵༆༒〘🔊〙Voice Chats༒༆࿐ཽ༵☆": [
                    "「🔊」General Chat",
                    "「😴」Afk",
                    "「🎵」Music",
                    "「🎮」Gaming",
                    "「🔴」Streams",
                ],
            }

            roles = [
                ("Owner", 0xFFF700),
                ("Co-Owner", 0x09FF00),
                ("Community Manager", 0x00AAFF),
                ("Manager", 0xFF8000),
                ("Administrator", 0xFF1100),
                ("Moderator", 0xA600FF),
                ("Trial Moderator", 0xFFDD00),
                ("Bots", 0xFF00F7),
                ("Vip", 0xF3FC74),
                ("Members", 0x81DEBF),
                ("Announcement Ping", 0xFC8674),
                ("Important Ping", 0x7496FC),
                ("Chat Revive Ping", 0x74FC7D),
            ]

        # ===========================
        # 3. Create roles with perms
        # ===========================
        role_objs = {}
        for name, color in roles:
            perms = discord.Permissions.none()

            if name.lower() in ["owner", "co-owner"]:
                perms = discord.Permissions.all()
            elif "admin" in name.lower() or "manager" in name.lower():
                perms.update(
                    manage_guild=True,
                    ban_members=True,
                    kick_members=True,
                    manage_channels=True,
                    manage_roles=True,
                )
            elif "moderator" in name.lower():
                perms.update(
                    manage_messages=True,
                    kick_members=True,
                    mute_members=True,
                )
            elif name.lower() == "bots":
                perms.update(
                    manage_webhooks=True,
                    send_messages=True,
                )
            elif name.lower() == "member" or name.lower() == "colorless":
                perms = discord.Permissions(send_messages=True, read_messages=True)

            try:
                role = await guild.create_role(
                    name=name,
                    colour=discord.Colour(color) if color else discord.Colour.default(),
                    permissions=perms,
                )
                role_objs[name] = role
            except Exception:
                continue

        # ===========================
        # 4. Create categories & channels
        # ===========================
        for cat_name, chans in categories.items():
            try:
                category = await guild.create_category(cat_name)
                for ch in chans:
                    if "🔊" in ch.lower() or "voice" in ch.lower():
                        await guild.create_voice_channel(ch, category=category)
                    else:
                        await guild.create_text_channel(ch, category=category)
            except Exception:
                continue

        # ===========================
        # 5. Reorder roles properly
        # ===========================
        positions = {}
        all_roles = list(guild.roles)  # default @everyone + new ones
        start_position = len(all_roles)

        for i, (name, _) in enumerate(roles):
            if name in role_objs:
                positions[role_objs[name]] = start_position - i

        try:
            await guild.edit_role_positions(positions=positions)
        except Exception:
            pass

        await ctx.send(f"✅ Finished rebuilding server with **{mode.title()}** mode!")

async def setup(bot):
    await bot.add_cog(ServerFix(bot))