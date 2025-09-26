import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re

CONFIG_FILE = "/data/welcome_config.json"
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
        self.config = load_config()

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
        gid = str(member.guild.id)
        settings = self.config.get(gid, {}).get(event_type)
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
                url = url.replace("{server_icon}", str(member.guild.icon.url) if member.guild.icon else "")
                await channel.send(url)

        elif settings.get("mode") == "embed":
            title = format_placeholders(settings.get("title"), member) or discord.Embed.Empty
            desc = format_placeholders(settings.get("description"), member) or discord.Embed.Empty
            color = int(settings.get("color", "0x00ff00"), 16)

            embed = discord.Embed(title=title, description=desc, color=color)

            # Replace image placeholders
            for key in ["image_url", "thumbnail_url", "icon_url"]:
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
    # HELPER FUNCTIONS
    # ======================
    async def ask(self, dm, user, question, allow_skip=False, show_placeholders=False, history=None):
        """Ask text question with back support."""
        if history is None:
            history = []
        hint = "\n(Type 'back' to go to the previous step)" if history else ""
        if allow_skip:
            question += "\n(Say 'skip' if you don't want this feature.)"
        if show_placeholders:
            question += "\nAvailable placeholders: {mention}, {user}, {server}, {count}"
        question += hint
        await dm.send(question)

        while True:
            msg = await self.bot.wait_for("message", check=lambda m: m.author == user and m.channel == dm)
            content = msg.content.strip()
            if content.lower() == "back" and history:
                return "back"
            if allow_skip and content.lower() == "skip":
                return None
            return content

    async def ask_image(self, dm, user, question, member, history=None, allow_skip=True):
        """Ask for image with back support."""
        if history is None:
            history = []
        hint = "\n(Type 'back' to go to the previous step)" if history else ""
        if allow_skip:
            question += "\n(Say 'skip' if you don't want this feature.)"
        question += "\nAvailable placeholders for image URLs: {member_pfp}, {server_icon}"
        question += hint
        await dm.send(question)

        while True:
            msg = await self.bot.wait_for("message", check=lambda m: m.author == user and m.channel == dm)
            content = msg.content.strip()

            if content.lower() == "back" and history:
                return "back"

            if allow_skip and content.lower() == "skip":
                return None

            # Accept placeholders
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

            await dm.send("❌ That is not a valid image/image link. Please upload an image, paste a direct image URL, or use a valid placeholder.")

    # ======================
    # SETUP WIZARD
    # ======================
    async def start_setup(self, user: discord.User, guild: discord.Guild, event_type: str):
        try:
            dm = await user.create_dm()
            await dm.send(f"⚙️ Let's set up **{event_type}** messages for `{guild.name}`!")

            wizard_history = []
            steps = []

            # CHANNEL
            while True:
                channel_id = await self.ask(dm, user, "Provide the **Channel ID** where messages should be sent.", history=wizard_history)
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
                mode = await self.ask(dm, user, "Do you want a `text` message or an `embed`?", history=wizard_history)
                if mode == "back":
                    wizard_history.pop()
                    channel_id = wizard_history[-1]["value"]
                    continue
                mode = mode.lower()
                if mode not in ["text", "embed"]:
                    await dm.send("❌ Invalid choice. Enter 'text' or 'embed'.")
                    continue
                break
            wizard_history.append({"key": "mode", "value": mode})

            data = {"channel_id": channel_id, "mode": mode}

            if mode == "text":
                while True:
                    text_msg = await self.ask(dm, user, "Enter your **text message**.", history=wizard_history, show_placeholders=True)
                    if text_msg == "back":
                        wizard_history.pop()
                        mode = wizard_history[-1]["value"]
                        continue
                    data["text"] = text_msg
                    wizard_history.append({"key": "text", "value": text_msg})
                    break
                # Image
                while True:
                    img = await self.ask_image(dm, user, "Upload or paste an **image** for the message.", member=user, history=wizard_history)
                    if img == "back":
                        wizard_history.pop()
                        continue
                    data["image_url"] = img
                    wizard_history.append({"key": "image_url", "value": img})
                    break

            else:  # embed
                # Title
                while True:
                    title = await self.ask(dm, user, "Enter the **embed TITLE**.", allow_skip=True, show_placeholders=True, history=wizard_history)
                    if title == "back":
                        wizard_history.pop()
                        mode = wizard_history[-1]["value"]
                        continue
                    data["title"] = title
                    wizard_history.append({"key": "title", "value": title})
                    break

                # Description
                while True:
    color = await self.ask(dm, user, "Enter the **embed COLOR** in HEX (example: #00ff00).", allow_skip=True, history=wizard_history)
    
    if color == "back":
        if wizard_history:
            wizard_history.pop()  # remove current step
        break  # go back to previous step
    
    if not color:  # skip or empty
        data["color"] = "0x00ff00"
        wizard_history.append({"key": "color", "value": data["color"]})
        break
    
    # Validate HEX
    if color.startswith("#"):
        color_value = color.replace("#", "0x")
    else:
        color_value = color
    
    try:
        int(color_value, 16)
        data["color"] = color_value
        wizard_history.append({"key": "color", "value": color_value})
        break
    except ValueError:
        await dm.send("❌ Invalid HEX color. Example: #00ff00")

                # Image fields
                for key, q in [("image_url", "embed IMAGE (big bottom)"),
                               ("thumbnail_url", "embed THUMBNAIL (top-right)"),
                               ("icon_url", "embed ICON (author icon, top-left)")]:
                    while True:
                        img = await self.ask_image(dm, user, f"Upload or paste the **{q}**.", member=user, history=wizard_history)
                        if img == "back":
                            wizard_history.pop()
                            break  # go back to previous image field
                        data[key] = img
                        wizard_history.append({"key": key, "value": img})
                        break

            # Save
            gid = str(guild.id)
            self.config.setdefault(gid, {})
            self.config[gid][event_type] = data
            save_config(self.config)
            await dm.send(f"✅ Setup complete for **{event_type}** messages in <#{channel_id}>!")

        except discord.Forbidden:
            try:
                await user.send("❌ I couldn't DM you. Please enable DMs and try again.")
            except:
                pass

async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))