import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from discord import app_commands
from discord import Interaction
import logging
import pilmoji
import asyncio
import os
import random
import aiohttp
import io
import textwrap
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class General(commands.Cog):
    """General commands for the bot"""

    def __init__(self, bot):
        self.bot = bot
        self.deleted_messages = {}  # channel_id -> list of messages
        self.edited_messages = {}   # channel_id -> list of (before, after)

    # Say command (Prefix)
    @commands.command(name="say")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def say_prefix(self, ctx, *, message: str):
        """Make the bot say something"""
        await self._say_message(ctx, message, ctx.author)

    # Say command (Slash)
    @discord.app_commands.command(name="say", description="Make the bot say something")
    @discord.app_commands.describe(message="The message for the bot to say")
    @discord.app_commands.default_permissions(manage_messages=True)
    async def say_slash(self, interaction: discord.Interaction, message: str):
        """Make the bot say something (slash command)"""
        await self._say_message(interaction, message, interaction.user)

    async def _say_message(self, ctx_or_interaction, message: str, author):
        """Internal method to handle say functionality"""
        # Basic content filtering
        if "@everyone" in message.lower() or "@here" in message.lower():
            await self._send_response(ctx_or_interaction, "❌ Cannot use everyone or here mentions!")
            return

        # Check message length
        if len(message) > 2000:
            await self.send_message(ctx_or_interaction, "❌ Message is too long! (Max 2000 characters)")
            return

        if len(message.strip()) == 0:
            await self.send_message(ctx_or_interaction, "❌ Message cannot be empty!")
            return

        try:
            # Delete the original command if it's a prefix command
            if isinstance(ctx_or_interaction, commands.Context):
                try:
                    await ctx_or_interaction.message.delete()
                except:
                    pass

            # Send the message to the channel
            await ctx_or_interaction.channel.send(message)

            # Log the action
            channel_name = getattr(ctx_or_interaction.channel, 'name', 'DM')
            logger.info(f"Say command used by {author} in #{channel_name}: {message[:50]}...")

            # Send confirmation for slash command AFTER sending the message
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.response.send_message("✅ Message sent!", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in say command: {e}")
            # Handle errors properly
            if isinstance(ctx_or_interaction, discord.Interaction):
                try:
                    if not ctx_or_interaction.response.is_done():
                        await ctx_or_interaction.response.send_message("❌ An error occurred while sending the message!", ephemeral=True)
                    else:
                        await ctx_or_interaction.followup.send("❌ An error occurred while sending the message!", ephemeral=True)
                except:
                    pass
            else:
                try:
                    await ctx_or_interaction.send("❌ An error occurred while sending the message!")
                except:
                    pass

    # --- Help command (Prefix) ---
    @commands.command(name="help")
    async def help_prefix(self, ctx, command_name: str = None):
        await self._show_help(ctx, command_name)

    # --- Help command (Slash) ---
    @discord.app_commands.command(name="help", description="Show help information")
    @discord.app_commands.describe(command="Specific command to get help for")
    async def help_slash(self, interaction: discord.Interaction, command: str = None):
        await self._show_help(interaction, command)

    # --- Internal helper ---
    async def _show_help(self, ctx_or_interaction, command_name: str = None):
        embed = discord.Embed(
            title="🤖 Bot Help",
            color=Config.COLORS.get("info", discord.Color.blue()),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Prefix: {Config.PREFIX} | Slash commands also available")

        # --- All commands info ---
        commands_info = {
            "kick": ("🦵 Kick", f"`{Config.PREFIX}kick <member> [reason]` or `/kick`\nKick a member from the server"),
            "ban": ("🔨 Ban", f"`{Config.PREFIX}ban <member> [reason]` or `/ban`\nBan a member from the server"),
            "mute": ("🔇 Mute", f"`{Config.PREFIX}mute <member> [duration] [reason]` or `/mute`\nMute a member (ex: 5m,2h,1d)"),
            "unmute": ("🔊 Unmute", f"`{Config.PREFIX}unmute <member>` or `/unmute`\nRemove timeout from a member"),
            "unban": ("✅ Unban", f"`{Config.PREFIX}unban <user_id> [reason]` or `/unban`\nUnban a user by ID"),
            "purge": ("🧹 Purge", f"`{Config.PREFIX}purge <amount>` or `/purge`\nDelete messages (default: 10, max: 100)"),
            "say": ("💬 Say", f"`{Config.PREFIX}say <message>` or `/say`\nMake the bot say something"),
            "giverole": ("➕ Give Role", f"`{Config.PREFIX}giverole <member> <role_name>` or `/giverole`\nGive a role"),
            "takerole": ("➖ Remove Role", f"`{Config.PREFIX}takerole <member> <role_name>` or `/takerole`\nRemove a role"),
            "deletechannel": ("🗑️ Delete Channel", f"`{Config.PREFIX}deletechannel <channel>` or `/deletechannel`\nRemove a channel"),
            "renamechannel": ("✏️ Rename Channel", f"`{Config.PREFIX}renamechannel <channel> <new_name>` or `/renamechannel`\nRename a channel"),
            "listroles": ("📜 List Roles", f"`{Config.PREFIX}listroles` or `/listroles`\nList all roles"),
            "saylogs": ("📝 Say Logs", f"`{Config.PREFIX}saylogs <message>` or `/saylogs`\nSend logs for the say command"),
            "snipe": ("🕵️‍♂️ Snipe", f"`{Config.PREFIX}snipe` or `/snipe`\nSee the last deleted message"),
            "editsnipe": ("✏️ Edit Snipe", f"`{Config.PREFIX}editsnipe` or `/editsnipe`\nSee the last edited message"),
            "ship": ("💘 Ship", f"`{Config.PREFIX}ship <member1> <member2>` or `/ship`\nShip two users"),
            "randomnumber": ("🎲 Random Number", f"`{Config.PREFIX}randomnumber <max>` or `/randomnumber`\nGenerate a random number"),
            "kiss": ("😘 Kiss", f"`{Config.PREFIX}kiss <member>` or `/kiss`\nKiss a member"),
            "invite": ("🔗 Invite", f"`{Config.PREFIX}invite` or `/invite`\nGet the bot invite link"),
            "ping": ("🏓 Ping", f"`{Config.PREFIX}ping` or `/ping`\nCheck bot latency"),
            "info": ("ℹ️ Info", f"`{Config.PREFIX}info` or `/info`\nGet bot information"),
            "avatar": ("🖼️ Avatar", f"`{Config.PREFIX}avatar <member>` or `/avatar`\nShow a user's avatar"),
            "8ball": ("🎱 8Ball", f"`{Config.PREFIX}8ball <question>` or `/8ball`\nPlay a game of 8ball"),
            "rolerename": ("📝 RoleRename", f"`{Config.PREFIX}rolerename <role> <new name>` or `/rolerename`\nRename a role in the server"),
            "tictactoe": ("📝 TicTacToe (XOXO)", f"`{Config.PREFIX}xoxo <member>` or `/tictactoe`\nPlay a game of TicTacToe (XOXO) with another user"),
            "rolecolor": ("🖍️ RoleColor", f"`{Config.PREFIX}rolecolor <role> <colorname/hex code>` or `/rolecolor`\nRecolor any role you want with hex code or color name"),
            "rolecolors": ("🌈 RoleColors", f"`{Config.PREFIX}rolecolors` or `/rolecolors`\nShows a list of the available colors"),
            "reactionrole": ("🎭 ReactionRole", f"`{Config.PREFIX}reactionrole <message id> <emoji> <role>` or `/reactionrole`\nAdd a reaction role to a message"),
            "saychecklogs": ("💬 SayCheckLogs", f"`{Config.PREFIX}saychecklogs` or `/saychecklogs`\nChecks which channel have the say command logs"),
            "serverinfo": ("❓ ServerInfo", f"`{Config.PREFIX}serverinfo` or `/serverinfo`\nCheck info about the server")
        }

        # --- Show specific command help ---
        if command_name:
            cmd_key = command_name.lower()
            if cmd_key in commands_info:
                name, desc = commands_info[cmd_key]
                embed.add_field(name=name, value=desc, inline=False)
            else:
                embed.description = f"❌ Command `{command_name}` not found!"

        # --- Show general help ---
        else:
            embed.description = f"A powerful moderation bot with both prefix (`{Config.PREFIX}`) and slash (`/`) commands."
            embed.add_field(
                name="🛡️ Moderation Commands",
                value=(
                    f"`{Config.PREFIX}kick` - Kick a member\n"
                    f"`{Config.PREFIX}ban` - Ban a member\n"
                    f"`{Config.PREFIX}unban` - Unban a user by ID\n"
                    f"`{Config.PREFIX}mute` - Mute a member\n"
                    f"`{Config.PREFIX}unmute` - Unmute a member\n"
                    f"`{Config.PREFIX}purge` - Delete messages\n"
                    f"`{Config.PREFIX}giverole` - Give role to member\n"
                    f"`{Config.PREFIX}takerole` - Remove role from member\n"
                    f"`{Config.PREFIX}deletechannel` - Remove a channel\n"
                    f"`{Config.PREFIX}renamechannel` - Rename a channel\n"
                    f"`{Config.PREFIX}listroles` - List all roles\n"
                    f"`{Config.PREFIX}saylogs` - Logs for say command\n"
                    f"`{Config.PREFIX}rolerename` - Rename a role in the server\n"
                    f"`{Config.PREFIX}rolecolor` - Change a color of a role with hex or color name\n"
                    f"`{Config.PREFIX}rolecolors` - Shows you a list of all the available colors\n"
                    f"`{Config.PREFIX}reactionrole` - Adds a reaction role to a message\n"
                    f"`{Config.PREFIX}saychecklogs` - Checks for the say command logging channel"
                ),
                inline=True
            )

            embed.add_field(
                name="💬 General Commands",
                value=(
                    f"`{Config.PREFIX}say` - Make bot say something\n"
                    f"`{Config.PREFIX}help` - Show this help\n"
                    f"`{Config.PREFIX}ping` - Check bot latency\n"
                    f"`{Config.PREFIX}info` - Bot information\n"
                    f"`{Config.PREFIX}avatar` - Show a user's avatar\n"
                    f"`{Config.PREFIX}8ball` - Play 8ball\n"
                    f"`{Config.PREFIX}ship` - Ship 2 users\n"
                    f"`{Config.PREFIX}snipe` - Last deleted message\n"
                    f"`{Config.PREFIX}editsnipe` - Last edited message\n"
                    f"`{Config.PREFIX}randomnumber` - Generate a random number\n"
                    f"`{Config.PREFIX}invite` - Get the bot invite link\n"
                    f"`{Config.PREFIX}kiss` - Kiss a member\n"
                    f"`{Config.PREFIX}tictactoe` - Challenge another user to TicTacToe (XO)\n"
                    f"`{Config.PREFIX}serverinfo` - View the whole server info. like members/bots/boosts/etc."
                ),
                inline=True
            )



            embed.add_field(
                name="ℹ️ Usage Notes",
                value="• All commands work with `/` slash commands too\n"
                      "• Moderation commands require appropriate permissions\n"
                      f"• Use `{Config.PREFIX}help <command>` for detailed help",
                inline=False
            )

        # --- Send embed safely ---
        await self._send_response(ctx_or_interaction, embed=embed)

    # --- Safe send helper ---
    async def _send_response(self, ctx_or_interaction, embed: discord.Embed = None, ephemeral: bool = False):
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(embed=embed)
        elif isinstance(ctx_or_interaction, discord.Interaction):
            if not ctx_or_interaction.response.is_done():
                await ctx_or_interaction.response.send_message(embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_interaction.followup.send(embed=embed, ephemeral=ephemeral)

    
    # Ping command (Prefix)
    @commands.command(name="ping")
    async def ping_prefix(self, ctx):
        """Check bot latency"""
        await self._show_ping(ctx)

    # Ping command (Slash)
    @discord.app_commands.command(name="ping", description="Check bot latency")
    async def ping_slash(self, interaction: discord.Interaction):
        """Check bot latency (slash command)"""
        await self._show_ping(interaction)

    async def _show_ping(self, ctx_or_interaction):
        """Internal method to handle ping functionality"""
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=Config.COLORS["success"] if latency < 100 else Config.COLORS["warning"],
            timestamp=datetime.utcnow()
        )

        await self._send_response(ctx_or_interaction, embed=embed)

    # Prefix command
    @commands.command(name="avatar")
    async def avatar(self, ctx, user: discord.User = None):
        user = user or ctx.author
        embed = discord.Embed(title=f"{user.name}'s Avatar", color=discord.Color.blue())
        embed.set_image(url=user.display_avatar.url)
        await ctx.send(embed=embed)

    # Slash command
    @app_commands.command(name="avatar", description="Shows the avatar of a user")
    @app_commands.describe(user="The user you want the avatar of")
    async def avatar_slash(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        embed = discord.Embed(title=f"{user.name}'s Avatar", color=discord.Color.blue())
        embed.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)


    # List of responses
    responses = [
        "🎱 Yes, definitely!",
        "🎱 No, sorry.",
        "🎱 Ask again later.",
        "🎱 It is certain.",
        "🎱 Very doubtful.",
        "🎱 Without a doubt!",
        "🎱 My sources say no.",
        "🎱 Signs point to yes.",
        "🎱 Better not tell you now.",
        "🎱 Cannot predict now.",
        "🎱 Yeah bro idfk.",
        "🎱 Do i look like i know?.",
        "🎱 BRO WTF IS THIS.",
        "🎱 sybau.",
        "🎱 Nuh Uh.",
        "🎱 Yuh Uh.",
        "🎱 Maybe bro.",
        "🎱 YESSIR."
    ]

    # Text command: $8ball
    @commands.command(name="8ball")
    async def eightball_command(self, ctx, *, question: str = None):
        if not question:
            await ctx.send(f" {ctx.author.mention} ❓ Please ask a question!")
            return
        response = random.choice(self.responses)
        await ctx.send(f"❓ {ctx.author.mention}\n{question}\n{response}")

    # Slash command: /8ball
    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    async def eightball_slash(self, interaction: discord.Interaction, question: str):
        response = random.choice(self.responses)
        await interaction.response.send_message(f"❓{question}\n{response}")

    # --- Ship Command (Prefix) ---
    @commands.command(name="ship")
    async def ship_prefix(self, ctx, member1: discord.Member, member2: discord.Member):
        await self.do_ship(ctx, member1, member2, slash=False)

    # --- Ship Command (Slash) ---
    @app_commands.command(name="ship", description="Ship two users together 💘")
    async def ship_slash(self, interaction: discord.Interaction, member1: discord.Member, member2: discord.Member):
        await self.do_ship(interaction, member1, member2, slash=True)

    # --- Main Function (used by both) ---
    async def do_ship(self, ctx_or_inter, member1, member2, slash=False):

        percentage = random.randint(0, 100)

        # Hearts bar for the embed
        hearts = int(percentage / 10)
        bar = "💖" * hearts + "💔" * (10 - hearts)

        # Ship name
        name1, name2 = member1.name, member2.name
        ship_name = name1[:len(name1)//2] + name2[len(name2)//2:]

        # --- Build the image ---
        W, H = 1000, 600
        AV_SIZE = 280
        LEFT_X = 140
        TOP_Y = 150
        RIGHT_X = W - LEFT_X - AV_SIZE
        CENTER_X = W // 2

        # Random pastel background
        def pastel_component(): return random.randint(180, 255)
        bg_color = (pastel_component(), pastel_component(), pastel_component(), 255)
        base = Image.new("RGBA", (W, H), bg_color)
        draw = ImageDraw.Draw(base)

        # Function to make image circular
        def make_circular(img):
            size = img.size
            mask = Image.new('L', size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0) + size, fill=255)

            circular_img = Image.new('RGBA', size, (0, 0, 0, 0))
            circular_img.paste(img, (0, 0))
            circular_img.putalpha(mask)
            return circular_img

        # Fetch avatars and make them circular
        async with aiohttp.ClientSession() as session:
            async with session.get(member1.display_avatar.url) as resp:
                avatar1 = Image.open(io.BytesIO(await resp.read())).convert("RGBA").resize((AV_SIZE, AV_SIZE))
                avatar1 = make_circular(avatar1)
            async with session.get(member2.display_avatar.url) as resp:
                avatar2 = Image.open(io.BytesIO(await resp.read())).convert("RGBA").resize((AV_SIZE, AV_SIZE))
                avatar2 = make_circular(avatar2)

        # Paste avatars
        base.paste(avatar1, (LEFT_X, TOP_Y), avatar1)
        base.paste(avatar2, (RIGHT_X, TOP_Y), avatar2)

        # ---------- FONT LOADING + BIG-TEXT FALLBACK ----------
        # Candidate font names/paths (we try them in order)
        REG_CANDIDATES  = [
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "arial.ttf",
            "NotoSans-Regular.ttf"
        ]
        BOLD_CANDIDATES = [
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "arialbd.ttf",
            "NotoSans-Bold.ttf"
        ]

        def try_truetype(paths, size):
            # Try each candidate path/name. Some environments let truetype accept just the filename.
            for p in paths:
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
            return None

        def draw_text_big(img, xy, text, size, *, bold=False,
                          fill=(255, 255, 255, 255), stroke_width=0,
                          stroke_fill=(0, 0, 0, 255), anchor="mm"):
            """Renders big text. Uses real TTF if found; otherwise draws bitmap text scaled up."""
            font = try_truetype(BOLD_CANDIDATES if bold else REG_CANDIDATES, size)
            d = ImageDraw.Draw(img)
            if font:
                d.text(xy, text, font=font, fill=fill,
                       stroke_width=stroke_width, stroke_fill=stroke_fill, anchor=anchor)
                return

            # Fallback: scale up bitmap font (ImageFont.load_default())
            base_font = ImageFont.load_default()
            # estimate scale factor (default font ~11-12 px). Use integer scale
            scale = max(2, int(size / 8))
            # Render small then scale nearest-neighbor to preserve sharpness
            # first get bbox for the small font
            temp = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            td = ImageDraw.Draw(temp)
            bbox = td.textbbox((0, 0), text, font=base_font)
            w, h = bbox[2] - bbox[0] + 6, bbox[3] - bbox[1] + 6
            temp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            td = ImageDraw.Draw(temp)
            # draw stroke by drawing multiple offsets (cheap)
            if stroke_width > 0:
                for ox in range(-stroke_width, stroke_width + 1):
                    for oy in range(-stroke_width, stroke_width + 1):
                        if ox == 0 and oy == 0:
                            continue
                        td.text((3 + ox, 3 + oy), text, font=base_font, fill=stroke_fill)
            td.text((3, 3), text, font=base_font, fill=fill)
            # scale up
            scaled = temp.resize((temp.width * scale, temp.height * scale), Image.NEAREST)
            # compute top-left placement for anchor="mm"
            x, y = xy
            if anchor == "mm":
                x = int(x - scaled.width / 2)
                y = int(y - scaled.height / 2)
            base.alpha_composite(scaled, (int(x), int(y)))

        # ---------- VECTOR HEART (always renders, no emoji needed) ----------
        def draw_vector_heart(canvas: Image.Image, center_xy, size_px,
                              fill=(255, 0, 0, 255), outline=(0, 0, 0, 255), outline_thickness=10):
            """Draw a heart composed of two circles + triangle; apply an outline via gaussian blur"""
            cx, cy = center_xy
            s = max(40, int(size_px))
            # Create heart mask (L mode)
            heart_mask = Image.new("L", (s, s), 0)
            hd = ImageDraw.Draw(heart_mask)

            # geometry values (simple proportions)
            r = s // 4
            top_y = s // 4
            left_x = s // 2 - 2 * r
            right_x = s // 2
            # two circles
            hd.ellipse([left_x, top_y - r, left_x + 2 * r, top_y + r], fill=255)
            hd.ellipse([right_x, top_y - r, right_x + 2 * r, top_y + r], fill=255)
            # triangle tip
            tip_y = s - max(4, s // 10)
            hd.polygon([(left_x, top_y + r // 2),
                        (right_x + 2 * r, top_y + r // 2),
                        (s // 2, tip_y)], fill=255)

            # Outline mask created by blurring the mask then thresholding
            # Normalize outline_thickness to reasonable blur radius
            radius = max(2, int(outline_thickness / 2))
            outline_mask = heart_mask.filter(ImageFilter.GaussianBlur(radius))
            # Create RGBA layers and paste
            ox = int(cx - s / 2)
            oy = int(cy - s / 2)

            # Paste outline (use outline_mask as alpha)
            outline_layer = Image.new("RGBA", (s, s), outline)
            canvas.paste(outline_layer, (ox, oy), outline_mask)
            # Paste fill
            fill_layer = Image.new("RGBA", (s, s), fill)
            canvas.paste(fill_layer, (ox, oy), heart_mask)

        # ---------- Draw everything (BIG sizes) ----------
        # Title with heart emojis (bigger and centered at top)
        with pilmoji.Pilmoji(base) as pilmoji_renderer:
            pilmoji_renderer.text((CENTER_X - 250, 30), "♥️Love Match♥️", font_size=120, emoji_size_factor=1.0)

        # Choose heart emoji based on percentage
        if percentage > 70:
            heart_emoji = "♥️"
        elif percentage >= 20:
            heart_emoji = "💛"
        else:
            heart_emoji = "💔"

        # Use pilmoji to render the heart emoji (much bigger and perfectly centered)
        with pilmoji.Pilmoji(base) as pilmoji_renderer:
            # Calculate position for perfectly centered emoji in the middle of the image
            emoji_x = CENTER_X - 120  # Adjust for much bigger emoji width
            emoji_y = H // 2 - 60  # Center vertically in the middle of the image
            pilmoji_renderer.text((emoji_x, emoji_y), heart_emoji, font_size=240, emoji_size_factor=1.0)

        # Percentage below heart (BIGGER)
        draw_text_big(base, (CENTER_X, H // 2 + 100), f"{percentage}%", 40, bold=True,
                      fill=(255, 255, 255, 255), stroke_width=8, stroke_fill=(0, 0, 0, 220), anchor="mm")

        # Usernames under pfps (closer to avatars)
        draw_text_big(base, (LEFT_X + AV_SIZE//2, TOP_Y + AV_SIZE + 20), member1.display_name, 20, bold=True,
                      fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 200), anchor="mm")
        draw_text_big(base, (RIGHT_X + AV_SIZE//2, TOP_Y + AV_SIZE + 20), member2.display_name, 20, bold=True,
                      fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 200), anchor="mm")

        # Save to buffer
        img_bytes = io.BytesIO()
        base.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        file = discord.File(img_bytes, filename="ship.png")

        # Embed (no image inside; image is attached above)
        embed = discord.Embed(
            title=f"💘 Shipping {name1} + {name2}",
            description=f"**Compatibility:** {percentage}%\n{bar}",
            color=discord.Color.random()
        )
        embed.add_field(name="💑 Ship Name", value=ship_name, inline=False)

        # Send in one message: image + embed
        if slash:
            await ctx_or_inter.response.send_message(file=file, embed=embed)
        else:
            await ctx_or_inter.send(file=file, embed=embed)

    # --- RandomNumber Command (Prefix) ---
    @commands.command(name="randomnumber")
    async def randomnumber_prefix(self, ctx, max_number: int):
        if max_number < 0:
            await ctx.send(f"{ctx.author.mention} ❌ Please enter a positive number.")
            return

        choice = random.randint(0, max_number)
        await ctx.send(f"🎲 {ctx.author.mention} Your random number between 0 and {max_number} is: **{choice}**")

    # --- RandomNumber Command (Slash) ---
    @app_commands.command(name="randomnumber", description="Pick a random number between 0 and your chosen max number")

    async def randomnumber_slash(self, interaction: discord.Interaction, max_number: int):
        if max_number < 0:
            await interaction.response.send_message("❌ Please enter a positive number.", ephemeral=True)
            return

        choice = random.randint(0, max_number)
        await interaction.response.send_message(f"🎲 Your random number between 0 and {max_number} is: **{choice}**")

    # --- Prefix command ---
    @commands.command(name="kiss")
    async def kiss_prefix(self, ctx, member: discord.Member):
        kiss_gifs = [
            "https://i.pinimg.com/originals/77/8d/51/778d51aca07848160ad9b52e6df37b30.gif",
            "https://gifdb.com/images/high/anime-kissing-498-x-280-gif-op3h5wkpm21z2dil.gif",
            "https://gifdb.com/images/high/surprising-anime-kiss-togashi-yuuta-q5960hphr79b0rwy.gif",
            "https://31.media.tumblr.com/ea7842aad07c00b098397bf4d00723c6/tumblr_n570yg0ZIv1rikkvpo1_500.gif",
            "https://i.pinimg.com/originals/28/62/37/2862374acd572ef4b1f2728e7e88962b.gif",
            "https://media3.giphy.com/media/v1.Y2lkPTZjMDliOTUyNGd5cG4wYTV4dng2YTQwM3lwdmVhYmZ1Mjk2dTNraTdrZXByODBldiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/bGm9FuBCGg4SY/source.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyY3dtN3lhaTB5b2Ixa3d2amtxdjNzZjNkMGZxZjk1NXlob3BjNTF4YyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/EVODaJHSXZGta/giphy.gif",
            "https://www.gifcen.com/wp-content/uploads/2022/03/anime-kiss-gif-7.gif",
            "https://www.icegif.com/wp-content/uploads/2022/08/icegif-1219.gif",
            "https://images.steamusercontent.com/ugc/775102481299729428/7468303EA0E2477C7CBD56914883C0C37AA97E40/?imw=5000&imh=5000&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false",
            "https://www.gifcen.com/wp-content/uploads/2022/03/anime-kiss-gif.gif",
            "https://i.pinimg.com/originals/10/5a/7a/105a7ad7edbe74e5ca834348025cc650.gif",
            "https://gifdb.com/images/high/anime-kissing-498-x-263-gif-psa9fpr8l6kipmoj.gif",
            "https://64.media.tumblr.com/84756421d21634f5f65d0d0f4c9da86f/tumblr_n2jz1jqEtq1sggrnxo1_500.gif",
            "https://64.media.tumblr.com/386629a5ea2079fb76dfc76e7216dec2/783ccc48501e3d96-b4/s540x810/3fa7d5db78585d42176f9ce4253fa05702be295b.gifv"
        ]
        gif = random.choice(kiss_gifs)
        color = discord.Color(random.randint(0, 0xFFFFFF))
        embed = discord.Embed(
            description=f"*{ctx.author.mention} kissed {member.mention}*",
            color=color
        )
        embed.set_image(url=gif)
        await ctx.send(embed=embed)

    # --- Slash command ---
    @app_commands.command(name="kiss", description="Send a kiss to a member")
    @app_commands.describe(member="The member you want to kiss")
    async def kiss_slash(self, interaction: discord.Interaction, member: discord.Member):
        kiss_gifs = [
            "https://i.pinimg.com/originals/77/8d/51/778d51aca07848160ad9b52e6df37b30.gif",
            "https://gifdb.com/images/high/anime-kissing-498-x-280-gif-op3h5wkpm21z2dil.gif",
            "https://gifdb.com/images/high/surprising-anime-kiss-togashi-yuuta-q5960hphr79b0rwy.gif",
            "https://31.media.tumblr.com/ea7842aad07c00b098397bf4d00723c6/tumblr_n570yg0ZIv1rikkvpo1_500.gif",
            "https://i.pinimg.com/originals/28/62/37/2862374acd572ef4b1f2728e7e88962b.gif",
            "https://media3.giphy.com/media/v1.Y2lkPTZjMDliOTUyNGd5cG4wYTV4dng2YTQwM3lwdmVhYmZ1Mjk2dTNraTdrZXByODBldiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/bGm9FuBCGg4SY/source.gif",
            "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyY3dtN3lhaTB5b2Ixa3d2amtxdjNzZjNkMGZxZjk1NXlob3BjNTF4YyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/EVODaJHSXZGta/giphy.gif",
            "https://www.gifcen.com/wp-content/uploads/2022/03/anime-kiss-gif-7.gif",
            "https://www.icegif.com/wp-content/uploads/2022/08/icegif-1219.gif",
            "https://images.steamusercontent.com/ugc/775102481299729428/7468303EA0E2477C7CBD56914883C0C37AA97E40/?imw=5000&imh=5000&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false",
            "https://www.gifcen.com/wp-content/uploads/2022/03/anime-kiss-gif.gif",
            "https://i.pinimg.com/originals/10/5a/7a/105a7ad7edbe74e5ca834348025cc650.gif",
            "https://gifdb.com/images/high/anime-kissing-498-x-263-gif-psa9fpr8l6kipmoj.gif",
            "https://64.media.tumblr.com/84756421d21634f5f65d0d0f4c9da86f/tumblr_n2jz1jqEtq1sggrnxo1_500.gif",
            "https://64.media.tumblr.com/386629a5ea2079fb76dfc76e7216dec2/783ccc48501e3d96-b4/s540x810/3fa7d5db78585d42176f9ce4253fa05702be295b.gifv"
        ]
        gif = random.choice(kiss_gifs)
        color = discord.Color(random.randint(0, 0xFFFFFF))
        embed = discord.Embed(
            description=f"*{interaction.user.mention} kissed {member.mention}*",
            color=color
        )
        embed.set_image(url=gif)
        await interaction.response.send_message(embed=embed)

    # --- Prefix command ---
@commands.command(name="fuck")
async def kiss_prefix(self, ctx, member: discord.Member):
    # Allowed users (inside function)
    ALLOWED_USERS = [123456789012345678, 987654321098765432]  # Replace with real IDs

    if ctx.author.id not in ALLOWED_USERS:
        return await ctx.send(f"❌ Sorry {ctx.author.mention}, you are not allowed to use this command.")

    kiss_gifs = [
        "https://i.pinimg.com/originals/77/8d/51/778d51aca07848160ad9b52e6df37b30.gif",
        "https://gifdb.com/images/high/anime-kissing-498-x-280-gif-op3h5wkpm21z2dil.gif",
        "https://gifdb.com/images/high/surprising-anime-kiss-togashi-yuuta-q5960hphr79b0rwy.gif",
        "https://31.media.tumblr.com/ea7842aad07c00b098397bf4d00723c6/tumblr_n570yg0ZIv1rikkvpo1_500.gif",
        "https://i.pinimg.com/originals/28/62/37/2862374acd572ef4b1f2728e7e88962b.gif",
        "https://media3.giphy.com/media/v1.Y2lkPTZjMDliOTUyNGd5cG4wYTV4dng2YTQwM3lwdmVhYmZ1Mjk2dTNraTdrZXByODBldiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/bGm9FuBCGg4SY/source.gif",
        "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyY3dtN3lhaTB5b2Ixa3d2amtxdjNzZjNkMGZxZjk1NXlob3BjNTF4YyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/EVODaJHSXZGta/giphy.gif",
        "https://www.gifcen.com/wp-content/uploads/2022/03/anime-kiss-gif-7.gif",
        "https://www.icegif.com/wp-content/uploads/2022/08/icegif-1219.gif",
        "https://images.steamusercontent.com/ugc/775102481299729428/7468303EA0E2477C7CBD56914883C0C37AA97E40/?imw=5000&imh=5000&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false",
        "https://www.gifcen.com/wp-content/uploads/2022/03/anime-kiss-gif.gif",
        "https://i.pinimg.com/originals/10/5a/7a/105a7ad7edbe74e5ca834348025cc650.gif",
        "https://gifdb.com/images/high/anime-kissing-498-x-263-gif-psa9fpr8l6kipmoj.gif",
        "https://64.media.tumblr.com/84756421d21634f5f65d0d0f4c9da86f/tumblr_n2jz1jqEtq1sggrnxo1_500.gif",
        "https://64.media.tumblr.com/386629a5ea2079fb76dfc76e7216dec2/783ccc48501e3d96-b4/s540x810/3fa7d5db78585d42176f9ce4253fa05702be295b.gifv"
    ]
    gif = random.choice(kiss_gifs)
    color = discord.Color(random.randint(0, 0xFFFFFF))
    embed = discord.Embed(
        description=f"*{ctx.author.mention} kissed {member.mention}*",
        color=color
    )
    embed.set_image(url=gif)
    await ctx.send(embed=embed)


# --- Slash command ---
    @app_commands.command(name="fuck", description="lowkey fuck someone")
    @app_commands.describe(member="The member you want to fuck")
    async def fuck_slash(self, interaction: Interaction, member: discord.Member):
        # Allowed users
        ALLOWED_USERS = [1167531276467708055, 1123292111404531783]  # Replace with real IDs

        if interaction.user.id not in ALLOWED_USERS:
            await interaction.response.send_message("🚫 You’re not allowed to use this command.", ephemeral=True)
            return

        await interaction.response.send_message(f"😘 {interaction.user.mention} kissed {member.mention}!")
        # Allowed users
        ALLOWED_USERS = [1167531276467708055, 1123292111404531783]  # Replace with real IDs

        if interaction.user.id not in ALLOWED_USERS:
            await interaction.response.send_message("🚫 You’re not allowed to use this command.", ephemeral=True)
            return

        await interaction.response.send_message(f"😘 {interaction.user.mention} kissed {member.mention}!")
    # Allowed users (inside function)
    ALLOWED_USERS = [1167531276467708055, 1123292111404531783]  # Replace with real IDs

    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message(
            f"❌ Sorry {interaction.user.mention}, you are not allowed to use this command.",
            ephemeral=True
        )

    fuck_gifs = [
        "https://cdn.hentaigifz.com/46199/animefuck001.gif",
        "https://el.phncdn.com/pics/gifs/046/726/901/(m=ldpwiqacxtE_Ai)(mh=WX86HgGsCMr_lBNi)46726901b.gif",
        "https://xporn-gifs.com/wp-content/uploads/2024/05/Anime-Hentai-Gif-3.gif",
        "https://otakusexart.com/wp-content/uploads/2019/09/hentai-onahole-doggystyle-sex-anime-fuck-gif.gif",
        "https://cdn.hentaigifz.com/2627/newyearsexgiftdrawnanime001.gif",
        "https://lh4.googleusercontent.com/proxy/9QuLrAksmg_Bz3jTvijY9hZybYrnYkBU7iL-3g20UjqCXhJVFn6D3LkWQsq-1Cl9hQ3L_a6miU6HNa0G_wKavdyMauXVQGXnvsvhAXzbXWqQBhzB5MNT8yumjQctgt3QQTjHUpNCe1rLfPlY0LJxaVSN2w",
        "https://myteenwebcam.com/fapp/gifs/521d40bc16d520b31110014dc80409a1.gif",
        "https://i.redd.it/6hu5hkt669xe1.gif",
        "https://lh4.googleusercontent.com/proxy/hiKIse2lfD8Sde5nBRFg5kpucT-GjTagpOMWuqy-kNIpaWauN2psV0A1Jvnj1W_6WuSG029eVBTuB8ybm-OLIpJpcG1udbnutuZncJlh1gWQsqngBJK5OaWugepPA5iqOojiWnwBnYsfjQNpRwEyAPV9jw",
        "https://el.phncdn.com/pics/gifs/049/821/161/(m=ldpwiqacxtE_Ai)(mh=yqDIRAxZNLyZAv7Y)49821161b.gif",
        "https://i.redd.it/b4iyikbzbv251.gif",
        "https://hentaiporns.net/r/entradas/2024/07/53cd3290e77694c9a0d0b3a1f3b5d59c.gif"
    ]
    gif = random.choice(fuck_gifs)
    color = discord.Color(random.randint(0, 0xFFFFFF))
    embed = discord.Embed(
        description=f"*{interaction.user.mention} fucked {member.mention}*",
        color=color
    )
    embed.set_image(url=gif)
    await interaction.response.send_message(embed=embed)



    # Info command (Prefix)
    @commands.command(name="info", aliases=["about"])
    async def info_prefix(self, ctx: commands.Context):
        """Show bot information"""
        await self._show_info(ctx)

    # Info command (Slash)
    @app_commands.command(name="info", description="Show bot information")
    async def info_slash(self, interaction: discord.Interaction):
        """Show bot information (slash command)"""
        await self._show_info(interaction)

    async def _show_info(self, ctx_or_interaction):
        """Internal method to handle info functionality"""
        embed = discord.Embed(
            title="🤖 Bot Information",
            color=Config.COLORS["info"],
            timestamp=datetime.utcnow()
        )

        embed.add_field(
            name="📊 Statistics",
            value=f"Servers: {len(self.bot.guilds)}\n"
                  f"Users: {len(self.bot.users)}\n"
                  f"Latency: {round(self.bot.latency * 1000)}ms",
            inline=True
        )

        embed.add_field(
            name="⚙️ Features",
            value="• Moderation commands\n"
                  "• Slash & prefix commands\n"
                  "• Permission management\n"
                  "• Message management\n"
                  "• User timeout system",
            inline=True
        )

        embed.add_field(
            name="🔧 Technical",
            value=f"Python: 3.8+\n"
                  f"discord.py: {discord.__version__}\n"
                  f"Prefix: `{Config.PREFIX}`\n"
                  f"Status: Online 24/7",
            inline=False
        )

        embed.set_footer(text="Made for 24/7 Discord moderation and fun :p")

        await self._send_response(ctx_or_interaction, embed=embed)

    async def _send_response(self, ctx_or_interaction, content=None, *, embed=None):
        """Send response to either prefix command or slash command"""
        if isinstance(ctx_or_interaction, commands.Context):
            if embed:
                await ctx_or_interaction.send(embed=embed)
            else:
                await ctx_or_interaction.send(content)
        else:
            if ctx_or_interaction.response.is_done():
                if embed:
                    await ctx_or_interaction.followup.send(embed=embed)
                else:
                    await ctx_or_interaction.followup.send(content)
            else:
                if embed:
                    await ctx_or_interaction.response.send_message(embed=embed)
                else:
                    await ctx_or_interaction.response.send_message(content)

        # ---------- Listeners ----------
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        if message.channel.id not in self.deleted_messages:
            self.deleted_messages[message.channel.id] = []
        self.deleted_messages[message.channel.id].append(message)
        # Keep only last 10 messages
        if len(self.deleted_messages[message.channel.id]) > 10:
            self.deleted_messages[message.channel.id].pop(0)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot:
            return
        if before.channel.id not in self.edited_messages:
            self.edited_messages[before.channel.id] = []
        self.edited_messages[before.channel.id].append((before, after))
        # Keep only last 10 messages
        if len(self.edited_messages[before.channel.id]) > 10:
            self.edited_messages[before.channel.id].pop(0)

    # ---------- Helper Functions ----------
    def build_deleted_embed(self, message):
        embed = discord.Embed(
            description=message.content or "Empty",
            color=discord.Color.red(),
            timestamp=message.created_at
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        return embed

    def build_edited_embed(self, data):
        before, after = data
        embed = discord.Embed(
            color=discord.Color.orange(),
            timestamp=after.edited_at
        )
        embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
        embed.add_field(name="Before", value=before.content or "Empty", inline=False)
        embed.add_field(name="After", value=after.content or "Empty", inline=False)
        return embed

    # ---------- Prefix Commands ----------
    @commands.command(name="snipe")
    async def snipe_prefix(self, ctx):
        """Shows the last deleted message in this channel."""
        deleted = self.deleted_messages.get(ctx.channel.id, [])
        edited = self.edited_messages.get(ctx.channel.id, [])
        if not deleted and not edited:
            return await ctx.send("No deleted or edited messages to snipe!")

        if deleted:
            embed = self.build_deleted_embed(deleted[-1])
            embed.set_footer(text=f"Deleted message 1/{len(deleted)}")
        else:
            embed = discord.Embed(
                description="No deleted messages yet.",
                color=discord.Color.red()
            )
        view = SnipeView(self, ctx.channel.id, mode="deleted")
        await ctx.send(embed=embed, view=view)

    @commands.command(name="editsnipe")
    async def editsnipe_prefix(self, ctx):
        """Shows the last edited message in this channel."""
        deleted = self.deleted_messages.get(ctx.channel.id, [])
        edited = self.edited_messages.get(ctx.channel.id, [])
        if not deleted and not edited:
            return await ctx.send("No deleted or edited messages to snipe!")

        if edited:
            embed = self.build_edited_embed(edited[-1])
            embed.set_footer(text=f"Edited message 1/{len(edited)}")
        else:
            embed = discord.Embed(
                description="No edited messages yet.",
                color=discord.Color.orange()
            )
        view = SnipeView(self, ctx.channel.id, mode="edited")
        await ctx.send(embed=embed, view=view)

    # ---------- Slash Commands ----------
    @app_commands.command(name="snipe", description="Shows the last deleted message in this channel")
    async def snipe_slash(self, interaction: discord.Interaction):
        deleted = self.deleted_messages.get(interaction.channel.id, [])
        edited = self.edited_messages.get(interaction.channel.id, [])
        if not deleted and not edited:
            return await interaction.response.send_message(
                "No deleted or edited messages to snipe!", ephemeral=True
            )

        if deleted:
            embed = self.build_deleted_embed(deleted[-1])
            embed.set_footer(text=f"Deleted message 1/{len(deleted)}")
        else:
            embed = discord.Embed(
                description="No deleted messages yet.",
                color=discord.Color.red()
            )
        view = SnipeView(self, interaction.channel.id, mode="deleted")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="editsnipe", description="Shows the last edited message in this channel")
    async def editsnipe_slash(self, interaction: discord.Interaction):
        deleted = self.deleted_messages.get(interaction.channel.id, [])
        edited = self.edited_messages.get(interaction.channel.id, [])
        if not deleted and not edited:
            return await interaction.response.send_message(
                "No deleted or edited messages to snipe!", ephemeral=True
            )

        if edited:
            embed = self.build_edited_embed(edited[-1])
            embed.set_footer(text=f"Edited message 1/{len(edited)}")
        else:
            embed = discord.Embed(
                description="No edited messages yet.",
                color=discord.Color.orange()
            )
        view = SnipeView(self, interaction.channel.id, mode="edited")
        await interaction.response.send_message(embed=embed, view=view)


# ---------- Buttons ----------
class SnipeView(discord.ui.View):
    def __init__(self, cog, channel_id, mode="deleted"):
        super().__init__(timeout=60)
        self.cog = cog
        self.channel_id = channel_id
        self.mode = mode  # "deleted" or "edited"
        self.current_index = 0

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.mode == "deleted":
            messages = self.cog.deleted_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No deleted messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index - 1) % len(messages)
            embed = self.cog.build_deleted_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Deleted message {self.current_index + 1}/{len(messages)}")
        else:
            messages = self.cog.edited_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No edited messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index - 1) % len(messages)
            embed = self.cog.build_edited_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Edited message {self.current_index + 1}/{len(messages)}")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.mode == "deleted":
            messages = self.cog.deleted_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No deleted messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index + 1) % len(messages)
            embed = self.cog.build_deleted_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Deleted message {self.current_index + 1}/{len(messages)}")
        else:
            messages = self.cog.edited_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No edited messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index + 1) % len(messages)
            embed = self.cog.build_edited_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Edited message {self.current_index + 1}/{len(messages)}")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Deleted", style=discord.ButtonStyle.red)
    async def deleted_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        messages = self.cog.deleted_messages.get(self.channel_id, [])
        if messages:
            self.mode = "deleted"
            self.current_index = 0
            embed = self.cog.build_deleted_embed(messages[-1])
            embed.set_footer(text=f"Deleted message 1/{len(messages)}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=discord.Embed(
                description="No deleted messages.",
                color=discord.Color.red()
            ), view=self)

    @discord.ui.button(label="Edited", style=discord.ButtonStyle.blurple)
    async def edited_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        messages = self.cog.edited_messages.get(self.channel_id, [])
        if messages:
            self.mode = "edited"
            self.current_index = 0
            embed = self.cog.build_edited_embed(messages[-1])
            embed.set_footer(text=f"Edited message 1/{len(messages)}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=discord.Embed(
                description="No edited messages.",
                color=discord.Color.orange()
            ), view=self)


async def setup(bot):
    await bot.add_cog(General(bot))
