import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re

CONFIG_FILE = "/data/welcome_config.json"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
QUESTION_COLOR = 0x2F3136
ERROR_COLOR = 0xFF0000
SUCCESS_COLOR = 0x00FF00


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {}


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def format_placeholders(template: str, member: discord.Member):
    if not template:
        return ""
    return (
        template.replace("{mention}", member.mention)
        .replace("{user}", str(member))
        .replace("{server}", member.guild.name)
        .replace("{count}", str(len(member.guild.members)))
    )


class WelcomeLeave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ======================
    # EVENTS
    # ======================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.handle_event(member, "join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.handle_event(member, "leave")

    async def handle_event(self, member: discord.Member, event_type: str):
        cfg = load_config()
        gid = str(member.guild.id)
        settings = cfg.get(gid, {}).get(event_type)
        if not settings:
            return

        channel = member.guild.get_channel(settings.get("channel_id"))
        if not channel or not channel.permissions_for(member.guild.me).send_messages:
            return

        if settings.get("mode") == "text":
            msg = format_placeholders(settings.get("text", ""), member)
            if msg:
                await channel.send(msg)
            img_url = settings.get("image_url")
            if img_url:
                img_url = img_url.replace("{member_pfp}", str(member.display_avatar.url))
                img_url = img_url.replace("{server_icon}", str(member.guild.icon.url) if member.guild.icon else "")
                await channel.send(img_url)
        elif settings.get("mode") == "embed":
            title = format_placeholders(settings.get("title"), member) or discord.Embed.Empty
            desc = format_placeholders(settings.get("description"), member) or discord.Embed.Empty
            try:
                color = int(settings.get("color", "0x00ff00"), 16)
            except ValueError:
                color = 0x00FF00
            embed = discord.Embed(title=title, description=desc, color=color)

            for key in ["image_url", "thumbnail_url", "icon_url", "footer_icon"]:
                if settings.get(key):
                    url = settings[key]
                    url = url.replace("{member_pfp}", str(member.display_avatar.url))
                    url = url.replace("{server_icon}", str(member.guild.icon.url) if member.guild.icon else "")
                    settings[key] = url

            if settings.get("image_url"):
                embed.set_image(url=settings["image_url"])
            if settings.get("thumbnail_url"):
                embed.set_thumbnail(url=settings["thumbnail_url"])
            if settings.get("icon_url"):
                embed.set_author(name=str(member), icon_url=settings["icon_url"])
            else:
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            if settings.get("footer_text") or settings.get("footer_icon"):
                embed.set_footer(
                    text=format_placeholders(settings.get("footer_text", ""), member),
                    icon_url=settings.get("footer_icon")
                )

            await channel.send(embed=embed)

    # ======================
    # COMMANDS: PREFIX
    # ======================
    @commands.command(name="join")
    async def join_setup_prefix(self, ctx):
        await self.start_setup(ctx.author, ctx.guild, "join")

    @commands.command(name="leave")
    async def leave_setup_prefix(self, ctx):
        await self.start_setup(ctx.author, ctx.guild, "leave")

    @commands.command(name="joinremove")
    async def join_remove_prefix(self, ctx):
        cfg = load_config()
        gid = str(ctx.guild.id)
        if cfg.get(gid, {}).pop("join", None) is not None:
            save_config(cfg)
            await ctx.send("✅ Join message configuration removed.")
        else:
            await ctx.send("❌ No join message configuration found.")

    @commands.command(name="leaveremove")
    async def leave_remove_prefix(self, ctx):
        cfg = load_config()
        gid = str(ctx.guild.id)
        if cfg.get(gid, {}).pop("leave", None) is not None:
            save_config(cfg)
            await ctx.send("✅ Leave message configuration removed.")
        else:
            await ctx.send("❌ No leave message configuration found.")

    # ======================
    # COMMANDS: SLASH
    # ======================
    @app_commands.command(name="join", description="Setup join messages (DM wizard)")
    async def join_setup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message("📩 Check your DMs to continue setup.", ephemeral=True)
        await self.start_setup(interaction.user, interaction.guild, "join")

    @app_commands.command(name="leave", description="Setup leave messages (DM wizard)")
    async def leave_setup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message("📩 Check your DMs to continue setup.", ephemeral=True)
        await self.start_setup(interaction.user, interaction.guild, "leave")

    @app_commands.command(name="joinremove", description="Remove join message config")
    async def join_remove_slash(self, interaction: discord.Interaction):
        cfg = load_config()
        gid = str(interaction.guild.id)
        if cfg.get(gid, {}).pop("join", None) is not None:
            save_config(cfg)
            await interaction.response.send_message("✅ Join message configuration removed.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No join message configuration found.", ephemeral=True)

    @app_commands.command(name="leaveremove", description="Remove leave message config")
    async def leave_remove_slash(self, interaction: discord.Interaction):
        cfg = load_config()
        gid = str(interaction.guild.id)
        if cfg.get(gid, {}).pop("leave", None) is not None:
            save_config(cfg)
            await interaction.response.send_message("✅ Leave message configuration removed.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No leave message configuration found.", ephemeral=True)

    # ======================
    # WIZARD INPUT HELPER
    # ======================
    async def ask_input(self, dm, user, title, description, *, allow_skip=False, placeholders=None, image=False):
        embed = discord.Embed(title=title, description=description, color=QUESTION_COLOR)
        if allow_skip:
            embed.add_field(name="⏭ Skip", value="Type `skip` to skip this step.", inline=False)
        embed.add_field(name="⏪ Back", value="Type `back` to return to previous step.", inline=False)
        if placeholders:
            embed.add_field(name="🔑 Placeholders", value=placeholders, inline=False)
        await dm.send(embed=embed)

        while True:
            msg = await self.bot.wait_for(
                "message", check=lambda m: m.author == user and m.channel == dm
            )
            content = msg.content.strip()

            if content.lower() == "back":
                return "back"
            if allow_skip and content.lower() == "skip":
                return None

            if image:
                if content.lower() in ("{member_pfp}", "{server_icon}"):
                    return content
                if msg.attachments:
                    att = msg.attachments[0]
                    if any(att.filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
                        return att.url
                    await dm.send(embed=discord.Embed(description="❌ Invalid attachment. Upload an image.", color=ERROR_COLOR))
                    continue
                if re.match(r"^https?://.*\.(png|jpg|jpeg|webp|gif)$", content, re.IGNORECASE):
                    return content
                await dm.send(embed=discord.Embed(description="❌ Invalid input. Provide an image URL or placeholder.", color=ERROR_COLOR))
            else:
                return content

    # ======================
    # WIZARD
    # ======================
    async def start_setup(self, user: discord.User, guild: discord.Guild, event_type: str):
        try:
            dm = await user.create_dm()
            await dm.send(embed=discord.Embed(title="⚙️ Setup Wizard", description=f"Let's configure **{event_type}** messages for `{guild.name}`!", color=QUESTION_COLOR))

            data = {}

            # Steps
            steps = []

            # Step 1: Channel (cannot skip/back)
            steps.append({"name": "Channel", "key": "channel_id", "prompt": "Provide the **Channel ID** where messages should be sent.", "allow_skip": False, "can_back": False, "image": False})

            # Step 2: Mode (can back, cannot skip)
            steps.append({"name": "Mode", "key": "mode", "prompt": "Do you want messages to be `text` or `embed`?", "allow_skip": False, "can_back": True, "image": False})

            index = 0
            while index < len(steps):
                step = steps[index]
                answer = await self.ask_input(dm, user, step["name"], step["prompt"], allow_skip=step["allow_skip"], image=step["image"])
                if answer == "back":
                    if step.get("can_back") and index > 0:
                        index -= 1
                        continue
                    else:
                        await dm.send(embed=discord.Embed(description="❌ Cannot go back from this step.", color=ERROR_COLOR))
                        continue
                if step["key"] == "channel_id":
                    try:
                        ch_id = int(answer)
                        ch_obj = guild.get_channel(ch_id)
                        if not ch_obj:
                            await dm.send(embed=discord.Embed(description="❌ Invalid channel ID.", color=ERROR_COLOR))
                        continue

                if step["key"] == "mode":
                    mode = answer.lower()
                    if mode not in ["text", "embed"]:
                        await dm.send(embed=discord.Embed(description="❌ Invalid mode. Choose `text` or `embed`.", color=ERROR_COLOR))
                        continue
                    answer = mode

                data[step["key"]] = answer
                index += 1

            # Now handle remaining steps based on mode
            if data["mode"] == "text":
                # Text message
                text_msg = await self.ask_input(dm, user, "Text Message", "Enter the text message for the join/leave event.", allow_skip=True, placeholders="{mention}, {user}, {server}, {count}")
                if text_msg != "back":
                    data["text"] = text_msg

                # Optional image
                img_msg = await self.ask_input(dm, user, "Image (optional)", "Upload or paste an image URL for the text message.", allow_skip=True, image=True, placeholders="{member_pfp}, {server_icon}")
                if img_msg != "back":
                    data["image_url"] = img_msg

            else:  # Embed mode
                embed_fields = [
                    ("title", "Embed Title", False),
                    ("description", "Embed Description", True),
                    ("color", "Embed Color (HEX like #00ff00)", True),
                    ("image_url", "Embed Image (bottom)", True),
                    ("thumbnail_url", "Embed Thumbnail (top-right)", True),
                    ("icon_url", "Embed Author Icon", True),
                    ("footer_text", "Embed Footer Text", True),
                    ("footer_icon", "Embed Footer Icon", True)
                ]
                for key, label, allow_skip in embed_fields:
                    while True:
                        answer = await self.ask_input(dm, user, label, f"Enter {label}.", allow_skip=allow_skip, placeholders="{member_pfp}, {server_icon}" if "url" in key or "icon" in key else "{mention}, {user}, {server}, {count}", image=("url" in key or "icon" in key))
                        if answer == "back":
                            break  # Go back to previous field
                        if key == "color" and answer:
                            color_val = answer.replace("#", "0x") if answer.startswith("#") else answer
                            try:
                                int(color_val, 16)
                                data[key] = color_val
                                break
                            except ValueError:
                                await dm.send(embed=discord.Embed(description="❌ Invalid HEX color. Example: #00ff00", color=ERROR_COLOR))
                                continue
                        else:
                            data[key] = answer
                            break

            # Save configuration
            cfg = load_config()
            gid = str(guild.id)
            cfg.setdefault(gid, {})
            cfg[gid][event_type] = data
            save_config(cfg)

            await dm.send(embed=discord.Embed(description=f"✅ Setup complete for **{event_type}** messages in <#{data['channel_id']}>!", color=SUCCESS_COLOR))

        except discord.Forbidden:
            try:
                await user.send("❌ I couldn't DM you. Please enable DMs and try again.")
            except:
                pass


async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))