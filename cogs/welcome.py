import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import os
import re

CONFIG_FILE = "welcome_config.json"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# Ensure config file exists
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({}, f, indent=4)

def load_config():
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def format_placeholders(template: str, member: discord.Member):
    if not template:
        return ""
    return (template.replace("{mention}", member.mention)
                    .replace("{user}", str(member))
                    .replace("{server}", member.guild.name)
                    .replace("{count}", str(len(member.guild.members))))

class WelcomeModal(ui.Modal):
    def __init__(self, bot: commands.Bot, guild: discord.Guild, event_type: str):
        super().__init__(title=f"{event_type.capitalize()} setup for {guild.name}")
        self.bot = bot
        self.guild = guild
        self.event_type = event_type

        # Fields
        self.channel_id_input = ui.TextInput(
            label="Channel ID",
            placeholder="123456789012345678",
            required=True,
            max_length=20
        )
        self.add_item(self.channel_id_input)

        self.mode_input = ui.TextInput(
            label="Mode: text or embed",
            placeholder="text",
            required=True,
            max_length=10
        )
        self.add_item(self.mode_input)

        # Text message
        self.text_input = ui.TextInput(
            label="Text message (if text mode)",
            placeholder="Welcome {mention} to {server}!",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        self.add_item(self.text_input)

        # Embed fields
        self.title_input = ui.TextInput(
            label="Embed Title",
            placeholder="Hello {mention}",
            required=False,
            max_length=256
        )
        self.add_item(self.title_input)

        self.desc_input = ui.TextInput(
            label="Embed Description",
            placeholder="Welcome {mention} to {server}!",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.desc_input)

        self.color_input = ui.TextInput(
            label="Embed Color HEX",
            placeholder="#00ff00",
            required=False,
            max_length=7
        )
        self.add_item(self.color_input)

        self.image_input = ui.TextInput(
            label="Embed Image URL / Attachment / {member_pfp} / {server_icon}",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        self.add_item(self.image_input)

        self.thumbnail_input = ui.TextInput(
            label="Embed Thumbnail URL / Attachment / {member_pfp} / {server_icon}",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        self.add_item(self.thumbnail_input)

        self.icon_input = ui.TextInput(
            label="Embed Author Icon URL / Attachment / {member_pfp} / {server_icon}",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000
        )
        self.add_item(self.icon_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate channel
        try:
            channel_id = int(self.channel_id_input.value.strip())
            channel = self.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)
                return
        except:
            await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)
            return

        mode = self.mode_input.value.strip().lower()
        if mode not in ["text", "embed"]:
            await interaction.response.send_message("❌ Mode must be 'text' or 'embed'.", ephemeral=True)
            return

        data = {"channel_id": channel_id, "mode": mode}

        if mode == "text":
            data["text"] = self.text_input.value or ""
            img = self.image_input.value.strip() if self.image_input.value else None
            data["image_url"] = img
        else:
            data["title"] = self.title_input.value or ""
            data["description"] = self.desc_input.value or ""
            color = self.color_input.value.strip()
            if color.startswith("#"):
                color = color.replace("#", "0x")
            data["color"] = color if color else "0x00ff00"
            data["image_url"] = self.image_input.value.strip() if self.image_input.value else None
            data["thumbnail_url"] = self.thumbnail_input.value.strip() if self.thumbnail_input.value else None
            data["icon_url"] = self.icon_input.value.strip() if self.icon_input.value else None

        # Save config
        cfg = load_config()
        gid = str(self.guild.id)
        cfg.setdefault(gid, {})
        cfg[gid][self.event_type] = data
        save_config(cfg)

        await interaction.response.send_message(f"✅ {self.event_type.capitalize()} setup saved in <#{channel_id}>!", ephemeral=True)


class WelcomeLeave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Events
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
        else:
            title = format_placeholders(settings.get("title"), member) or discord.Embed.Empty
            desc = format_placeholders(settings.get("description"), member) or discord.Embed.Empty
            color = int(settings.get("color", "0x00ff00"), 16)
            embed = discord.Embed(title=title, description=desc, color=color)

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

    # Commands
    @app_commands.command(name="join_setup", description="Setup join messages")
    async def join_setup(self, interaction: discord.Interaction):
        modal = WelcomeModal(self.bot, interaction.guild, "join")
        await interaction.response.send_modal(modal)

    @app_commands.command(name="leave_setup", description="Setup leave messages")
    async def leave_setup(self, interaction: discord.Interaction):
        modal = WelcomeModal(self.bot, interaction.guild, "leave")
        await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))