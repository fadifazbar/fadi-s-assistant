import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re

CONFIG_FILE = "welcome_config.json"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


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
    """Text placeholders only."""
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

            # Replace image placeholders
            for key in ["image_url", "thumbnail_url", "icon_url"]:
                if settings.get(key):
                    url = settings[key]
                    url = url.replace("{member_pfp}", str(member.display_avatar.url))
                    url = url.replace(
                        "{server_icon}", str(member.guild.icon.url) if member.guild.icon else ""
                    )
                    settings[key] = url

            if settings.get("image_url"):
                embed.set_image(url=settings["image_url"])
            if settings.get("thumbnail_url"):
                embed.set_thumbnail(url=settings["thumbnail_url"])
            if settings.get("icon_url"):
                embed.set_author(name=str(member), icon_url=settings["icon_url"])
            else:
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)

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
        await interaction.response.send_message(
            "📩 Check your DMs to continue setup.", ephemeral=True
        )
        await self.start_setup(interaction.user, interaction.guild, "join")

    @app_commands.command(name="leave", description="Setup leave messages (DM wizard)")
    async def leave_setup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "📩 Check your DMs to continue setup.", ephemeral=True
        )
        await self.start_setup(interaction.user, interaction.guild, "leave")

    # ======================
    # HELPER FUNCTIONS
    # ======================
    async def ask_input(
        self,
        dm,
        user,
        question,
        *,
        allow_skip=False,
        placeholders=None,
        image=False,
        history=None,
        member=None,
    ):
        """Unified input function for text or image with back/skip support."""
        if history is None:
            history = []
        hint = "\n(Type 'back' to go to the previous step)" if history else ""
        if allow_skip:
            question += "\n(Say 'skip' if you don't want this feature.)"
        if placeholders:
            question += f"\nAvailable placeholders: {placeholders}"
        question += hint
        await dm.send(question)

        while True:
            msg = await self.bot.wait_for(
                "message", check=lambda m: m.author == user and m.channel == dm
            )
            content = msg.content.strip()

            if content.lower() == "back" and history:
                return "back"
            if allow_skip and content.lower() == "skip":
                return None

            if image:
                # Image placeholders
                if content.lower() in ("{member_pfp}", "{server_icon}"):
                    return content
                # Attachment
                if msg.attachments:
                    url = msg.attachments[0].url
                    if url.lower().endswith(IMAGE_EXTENSIONS):
                        return url
                    else:
                        await dm.send("❌ That is not a valid image/image link.")
                        continue
                # URL check
                if re.match(r"^https?://.*\.(png|jpg|jpeg|webp|gif)$", content, re.IGNORECASE):
                    return content
                await dm.send(
                    "❌ Invalid input. Upload an image, paste a direct URL, or use a valid placeholder."
                )
            else:
                return content

    # ======================
    # SETUP WIZARD
    # ======================
    async def start_setup(self, user: discord.User, guild: discord.Guild, event_type: str):
        try:
            dm = await user.create_dm()
            await dm.send(f"⚙️ Let's set up **{event_type}** messages for `{guild.name}`!")

            wizard_history = []

            # CHANNEL
            while True:
                channel_id = await self.ask_input(
                    dm, user, "Provide the **Channel ID** where messages should be sent.", history=wizard_history
                )
                if channel_id == "back":
                    await dm.send("❌ This is the first question, cannot go back further.")
                    continue
                try:
                    channel_id = int(channel_id)
                    break
                except:
                    await dm.send("❌ Invalid channel ID. Please enter a valid number.")
            wizard_history.append({"key": "channel_id", "value": channel_id})

            # MODE
            while True:
                mode = await self.ask_input(
                    dm,
                    user,
                    "Do you want a `text` message or an `embed`?",
                    history=wizard_history,
                )
                if mode == "back":
                    wizard_history.pop()
                    continue
                mode = mode.lower()
                if mode not in ["text", "embed"]:
                    await dm.send("❌ Invalid choice. Enter 'text' or 'embed'.")
                    continue
                break
            wizard_history.append({"key": "mode", "value": mode})

            data = {"channel_id": channel_id, "mode": mode}

            if mode == "text":
                # TEXT
                text_msg = await self.ask_input(
                    dm,
                    user,
                    "Enter your **text message**.",
                    placeholders="{mention}, {user}, {server}, {count}",
                    history=wizard_history,
                )
                if text_msg == "back":
                    wizard_history.pop()
                else:
                    data["text"] = text_msg
                    wizard_history.append({"key": "text", "value": text_msg})

                # IMAGE
                img = await self.ask_input(
                    dm,
                    user,
                    "Upload or paste an **image** for the message.",
                    image=True,
                    placeholders="{member_pfp}, {server_icon}",
                    history=wizard_history,
                )
                if img == "back":
                    wizard_history.pop()
                else:
                    data["image_url"] = img
                    wizard_history.append({"key": "image_url", "value": img})

            else:  # embed
                # TITLE
                title = await self.ask_input(
                    dm,
                    user,
                    "Enter the **embed TITLE**.",
                    allow_skip=True,
                    placeholders="{mention}, {user}, {server}, {count}",
                    history=wizard_history,
                )
                if title == "back":
                    wizard_history.pop()
                else:
                    data["title"] = title
                    wizard_history.append({"key": "title", "value": title})

                # DESCRIPTION
                desc = await self.ask_input(
                    dm,
                    user,
                    "Enter the **embed DESCRIPTION**.",
                    allow_skip=True,
                    placeholders="{mention}, {user}, {server}, {count}",
                    history=wizard_history,
                )
                if desc == "back":
                    wizard_history.pop()
                else:
                    data["description"] = desc
                    wizard_history.append({"key": "description", "value": desc})

                # COLOR
                while True:
                    color = await self.ask_input(
                        dm,
                        user,
                        "Enter the **embed COLOR** in HEX (example: #00ff00).",
                        allow_skip=True,
                        history=wizard_history,
                    )
                    if color == "back":
                        wizard_history.pop()
                        break  # go back to previous step
                    if not color:
                        data["color"] = "0x00ff00"
                        break
                    color_value = color.replace("#", "0x") if color.startswith("#") else color
                    try:
                        int(color_value, 16)
                        data["color"] = color_value
                        break
                    except ValueError:
                        await dm.send("❌ Invalid HEX color. Example: #00ff00")

                # IMAGE FIELDS
                for key, q in [
                    ("image_url", "embed IMAGE (big bottom)"),
                    ("thumbnail_url", "embed THUMBNAIL (top-right)"),
                    ("icon_url", "embed ICON (author icon, top-left)"),
                ]:
                    while True:
                        img = await self.ask_input(
                            dm,
                            user,
                            f"Upload or paste the **{q}**.",
                            image=True,
                            placeholders="{member_pfp}, {server_icon}",
                            history=wizard_history,
                        )
                        if img == "back":
                            wizard_history.pop()
                            break  # go back to previous field
                        data[key] = img
                        wizard_history.append({"key": key, "value": img})
                        break

            # SAVE CONFIG
            cfg = load_config()
            gid = str(guild.id)
            cfg.setdefault(gid, {})
            cfg[gid][event_type] = data
            save_config(cfg)
            await dm.send(f"✅ Setup complete for **{event_type}** messages in <#{channel_id}>!")

        except discord.Forbidden:
            try:
                await user.send("❌ I couldn't DM you. Please enable DMs and try again.")
            except:
                pass


async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))