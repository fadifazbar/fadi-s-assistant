import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re

# ======================
# CONFIG
# ======================
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
    """Replace text placeholders with real values."""
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

        channel_id = settings.get("channel_id")
        channel = member.guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return

        perms = channel.permissions_for(member.guild.me)
        if not perms.send_messages:
            return

        if settings.get("mode") == "text":
            msg = format_placeholders(settings.get("text", "{mention} joined {server}!"), member)
            await channel.send(msg)

            if settings.get("image_url"):
                url = settings["image_url"]
                url = url.replace("{member_pfp}", str(member.display_avatar.url))
                url = url.replace(
                    "{server_icon}", str(member.guild.icon.url) if member.guild.icon else ""
                )
                await channel.send(url)

        elif settings.get("mode") == "embed":
            title = format_placeholders(settings.get("title"), member) or discord.Embed.Empty
            desc = format_placeholders(settings.get("description"), member) or discord.Embed.Empty

            try:
                color = int(settings.get("color", "0x00ff00"), 16)
            except ValueError:
                color = 0x00FF00

            embed = discord.Embed(title=title, description=desc, color=color)

            # Images & author
            for key in ["image_url", "thumbnail_url", "icon_url", "footer_icon"]:
                if settings.get(key):
                    url = settings[key]
                    url = url.replace("{member_pfp}", str(member.display_avatar.url))
                    url = url.replace(
                        "{server_icon}", str(member.guild.icon.url) if member.guild.icon else ""
                    )
                    settings[key] = url  # overwrite locally

            if settings.get("image_url"):
                embed.set_image(url=settings["image_url"])
            if settings.get("thumbnail_url"):
                embed.set_thumbnail(url=settings["thumbnail_url"])
            if settings.get("icon_url"):
                embed.set_author(name=str(member), icon_url=settings["icon_url"])
            else:
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)

            # Footer
            if settings.get("footer_text") or settings.get("footer_icon"):
                embed.set_footer(
                    text=format_placeholders(settings.get("footer_text", ""), member),
                    icon_url=settings.get("footer_icon"),
                )

            await channel.send(embed=embed)

    # ======================
    # PREFIX COMMANDS
    # ======================
    @commands.command(name="join")
    async def join_setup_prefix(self, ctx):
        await self.start_setup(ctx.author, ctx.guild, "join")

    @commands.command(name="leave")
    async def leave_setup_prefix(self, ctx):
        await self.start_setup(ctx.author, ctx.guild, "leave")

    # ======================
    # SLASH COMMANDS
    # ======================
    @app_commands.command(name="join", description="Setup join messages (DM wizard)")
    async def join_setup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message("📩 Check your DMs to continue setup.", ephemeral=True)
        await self.start_setup(interaction.user, interaction.guild, "join")

    @app_commands.command(name="leave", description="Setup leave messages (DM wizard)")
    async def leave_setup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message("📩 Check your DMs to continue setup.", ephemeral=True)
        await self.start_setup(interaction.user, interaction.guild, "leave")

    # ======================
    # EMBED INPUT HELPER
    # ======================
    async def ask_input(
        self,
        dm,
        user,
        title,
        description,
        *,
        allow_skip=False,
        placeholders=None,
        image=False,
    ):
        """Ask user for input using embeds, handle skip/back, validate images."""
        embed = discord.Embed(title=title, description=description, color=QUESTION_COLOR)

        if allow_skip:
            embed.add_field(name="⏭ Skip", value="Type `skip` to leave this blank.", inline=False)
        embed.add_field(name="⏪ Back", value="Type `back` to return to the previous step.", inline=False)

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
                    await dm.send(embed=discord.Embed(
                        description="❌ Invalid attachment. Please upload an image file.",
                        color=ERROR_COLOR
                    ))
                    continue
                if re.match(r"^https?://.*\.(png|jpg|jpeg|webp|gif)$", content, re.IGNORECASE):
                    return content
                await dm.send(embed=discord.Embed(
                    description="❌ Invalid input. Upload an image, paste a direct image URL, or use a placeholder.",
                    color=ERROR_COLOR
                ))
            else:
                return content

    # ======================
    # SETUP WIZARD (Embed-based)
    # ======================
    async def start_setup(self, user: discord.User, guild: discord.Guild, event_type: str):
        try:
            dm = await user.create_dm()
            await dm.send(embed=discord.Embed(
                title="⚙️ Setup Wizard",
                description=f"Let's configure **{event_type}** messages for `{guild.name}`!\n\nType `back` anytime to return to the previous step.",
                color=QUESTION_COLOR
            ))

            data = {}

            # CHANNEL
            while True:
                channel_id = await self.ask_input(
                    dm, user, "Step 1: Channel", "Provide the **Channel ID** where messages should be sent."
                )
                if channel_id == "back":
                    await dm.send(embed=discord.Embed(
                        description="❌ This is the first step. You can't go back.",
                        color=ERROR_COLOR
                    ))
                    continue
                try:
                    channel_id = int(channel_id)
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        await dm.send(embed=discord.Embed(
                            description="❌ I can't find that channel. Try again.",
                            color=ERROR_COLOR
                        ))
                        continue
                    break
                except ValueError:
                    await dm.send(embed=discord.Embed(
                        description="❌ Invalid channel ID. Please enter a number.",
                        color=ERROR_COLOR
                    ))
            data["channel_id"] = channel_id

            # MODE
            while True:
                mode = await self.ask_input(
                    dm, user, "Step 2: Mode", "Do you want messages to be `text` or `embed`?"
                )
                if mode == "back":
                    return await self.start_setup(user, guild, event_type)
                if mode.lower() not in ["text", "embed"]:
                    await dm.send(embed=discord.Embed(
                        description="❌ Enter either 'text' or 'embed'.",
                        color=ERROR_COLOR
                    ))
                    continue
                mode = mode.lower()
                break
            data["mode"] = mode

            if mode == "text":
                # TEXT MESSAGE
                text_msg = await self.ask_input(
                    dm, user, "Step 3: Text Message", "Enter your **text message**.",
                    placeholders="{mention}, {user}, {server}, {count}"
                )
                if text_msg == "back":
                    return await self.start_setup(user, guild, event_type)
                data["text"] = text_msg

                # IMAGE
                img = await self.ask_input(
                    dm, user, "Step 4: Image", "Upload or paste an **image** for the message.",
                    image=True, allow_skip=True, placeholders="{member_pfp}, {server_icon}"
                )
                if img == "back":
                    return await self.start_setup(user, guild, event_type)
                data["image_url"] = img

            else:  # EMBED
                embed_fields = [
                    ("title", "Embed TITLE", False),
                    ("description", "Embed DESCRIPTION", True),
                    ("color", "Embed COLOR (HEX like #00ff00)", True),
                    ("image_url", "Embed IMAGE (large bottom)", True),
                    ("thumbnail_url", "Embed THUMBNAIL (top-right)", True),
                    ("icon_url", "Embed ICON (author icon)", True),
                    ("footer_text", "Embed FOOTER text", True),
                    ("footer_icon", "Embed FOOTER image/icon", True),
                ]

                for key, label, allow_skip in embed_fields:
                    while True:
                        is_image = key.endswith("_url") or key.endswith("_icon")
                        answer = await self.ask_input(
                            dm,
                            user,
                            f"Embed Setup – {label}",
                            f"Enter the **{label}**.",
                            allow_skip=allow_skip,
                            placeholders="{mention}, {user}, {server}, {count}" if not is_image else "{member_pfp}, {server_icon}",
                            image=is_image,
                        )
                        if answer == "back":
                            return await self.start_setup(user, guild, event_type)

                        if key == "color":
                            if not answer:
                                data["color"] = "0x00ff00"
                            else:
                                color_val = answer.replace("#", "0x") if answer.startswith("#") else answer
                                try:
                                    int(color_val, 16)
                                    data["color"] = color_val
                                except ValueError:
                                    await dm.send(embed=discord.Embed(
                                        description="❌ Invalid HEX color. Example: #00ff00",
                                        color=ERROR_COLOR
                                    ))
                                    continue
                        else:
                            data[key] = answer
                        break

            # SAVE CONFIG
            cfg = load_config()
            gid = str(guild.id)
            cfg.setdefault(gid, {})
            cfg[gid][event_type] = data
            save_config(cfg)

            await dm.send(embed=discord.Embed(
                description=f"✅ Setup complete for **{event_type}** messages in <#{channel_id}>!",
                color=SUCCESS_COLOR
            ))

        except discord.Forbidden:
            try:
                await user.send("❌ I couldn't DM you. Please enable DMs and try again.")
            except:
                pass


async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))