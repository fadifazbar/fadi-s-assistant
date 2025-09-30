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

        guild = ctx.guild

        # === DELETE CHANNELS ===
        for channel in guild.channels:
            if channel.id == ctx.channel.id:
                continue  # don't delete the channel where the command was used
            try:
                await channel.delete()
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

        # === DELETE ROLES ===
        for role in guild.roles:
            if role.is_default() or role >= guild.me.top_role:
                continue  # skip @everyone and roles higher/equal than the bot
            try:
                await role.delete()
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

        # === SIMPLE MODE ===
        if mode == "simple":
            categories = {
                "Important": ["rules", "announcements", "welcome", "goodbye"],
                "Main": ["chat", "bot-cmds", "memes", "media"],
            }
            roles = [
                "Owner", "Co-Owner", "Admin", "Moderator",
                "Trial Moderator", "Bots", "Member"
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

        # === CREATE CATEGORIES + CHANNELS ===
        new_channels = []
        for cat_name, chans in categories.items():
            try:
                category = await guild.create_category(cat_name)
            except Exception:
                continue
            for chan in chans:
                try:
                    if "voice" in cat_name.lower() or "🔊" in cat_name:
                        ch = await guild.create_voice_channel(chan, category=category)
                    else:
                        ch = await guild.create_text_channel(chan, category=category)
                    new_channels.append(ch)
                except Exception:
                    continue

        # === CREATE ROLES (AND ORDER THEM) ===
        new_roles = []
        if mode == "simple":
            for r in roles:
                try:
                    role = await guild.create_role(name=r)
                    new_roles.append(role)
                except Exception:
                    continue
        else:
            for r, color in roles:
                try:
                    role = await guild.create_role(name=r, color=discord.Color(color))
                    new_roles.append(role)
                except Exception:
                    continue

            # Reorder roles in the same order they were created
            try:
                positions = {role: (len(new_roles) - i) for i, role in enumerate(new_roles)}
                await guild.edit_role_positions(positions=positions)
            except Exception:
                pass

        await ctx.send(f"✅ Successfully reset the server with **{mode.capitalize()}** mode!")

async def setup(bot):
    await bot.add_cog(FixServer(bot))