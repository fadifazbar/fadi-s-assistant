import discord
from discord.ext import commands
from discord import app_commands, Interactions
import json
import os
import re

CONFIG_FILE = "/data/welcome_config.json"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
QUESTION_COLOR = 0xFFB700
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
    # PREFIX COMMANDS
    # ======================
    # ======================
def has_manage_channels():
    async def predicate(ctx):
        if ctx.author.guild_permissions.manage_channels:
            return True
        await ctx.send("❌ You need the **Manage Channels** permission to use this command.", delete_after=10)
        return False
    return commands.check(predicate)

@commands.command(name="join")
@has_manage_channels()
async def join_setup_prefix(self, ctx):
    await self.start_setup(ctx.author, ctx.guild, "join")

@commands.command(name="leave")
@has_manage_channels()
async def leave_setup_prefix(self, ctx):
    await self.start_setup(ctx.author, ctx.guild, "leave")

@commands.command(name="joinremove")
@has_manage_channels()
async def join_remove_prefix(self, ctx):
    cfg = load_config()
    gid = str(ctx.guild.id)
    if cfg.get(gid, {}).pop("join", None) is not None:
        save_config(cfg)
        await ctx.send("✅ Join message configuration removed.")
    else:
        await ctx.send("❌ No join message configuration found.")

@commands.command(name="leaveremove")
@has_manage_channels()
async def leave_remove_prefix(self, ctx):
    cfg = load_config()
    gid = str(ctx.guild.id)
    if cfg.get(gid, {}).pop("leave", None) is not None:
        save_config(cfg)
        await ctx.send("✅ Leave message configuration removed.")
    else:
        await ctx.send("❌ No leave message configuration found.")

# ======================
# SLASH COMMANDS WITH PERMISSION CHECK
# ======================
def has_manage_channels_slash():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.manage_channels:
            return True
        await interaction.response.send_message("❌ You need the **Manage Channels** permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)

@app_commands.command(name="join", description="Setup join messages (DM wizard)")
@has_manage_channels_slash()
async def join_setup_slash(self, interaction):
    # interaction parameter has no type annotation
    await interaction.response.send_message("📩 Check your DMs to continue setup.", ephemeral=True)
    await self.start_setup(interaction.user, interaction.guild, "join")

@app_commands.command(name="leave", description="Setup leave messages (DM wizard)")
@has_manage_channels_slash()
async def leave_setup_slash(self, interaction):
    await interaction.response.send_message("📩 Check your DMs to continue setup.", ephemeral=True)
    await self.start_setup(interaction.user, interaction.guild, "leave")

@app_commands.command(name="joinremove", description="Remove join message config")
@has_manage_channels_slash()
async def join_remove_slash(self, interaction):
    cfg = load_config()
    gid = str(interaction.guild.id)
    if cfg.get(gid, {}).pop("join", None) is not None:
        save_config(cfg)
        await interaction.response.send_message("✅ Join message configuration removed.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ No join message configuration found.", ephemeral=True)

@app_commands.command(name="leaveremove", description="Remove leave message config")
@has_manage_channels_slash()
async def leave_remove_slash(self, interaction):
    cfg = load_config()
    gid = str(interaction.guild.id)
    if cfg.get(gid, {}).pop("leave", None) is not None:
        save_config(cfg)
        await interaction.response.send_message("✅ Leave message configuration removed.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ No leave message configuration found.", ephemeral=True)

    # ======================
    # INPUT HELPER
    # ======================
    async def ask_input(self, dm, user, title, description, *, allow_skip=False, placeholders=None, image=False, show_back=True):
        embed = discord.Embed(title=title, description=description, color=QUESTION_COLOR)
        if allow_skip:
            embed.add_field(name="⏭ Skip", value="Type `skip` to skip this step.", inline=False)
        if show_back:
            embed.add_field(name="⏪ Back", value="Type `back` to return to previous step.", inline=False)
        if placeholders:
            embed.add_field(name="🔑 Placeholders", value=placeholders, inline=False)
        await dm.send(embed=embed)

        while True:
            msg = await self.bot.wait_for(
                "message", check=lambda m: m.author == user and m.channel == dm
            )
            content = msg.content.strip()
            if show_back and content.lower() == "back":
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
            await dm.send(embed=discord.Embed(
                title="⚙️ Setup Wizard",
                description=f"Let's configure **{event_type}** messages for `{guild.name}`!",
                color=QUESTION_COLOR
            ))

            # Step 1: Channel ID
            while True:
                channel_input = await self.ask_input(dm, user, "Channel ID", "Provide the **Channel ID** where messages should be sent.", show_back=False)
                try:
                    channel_id = int(channel_input)
                    if not guild.get_channel(channel_id):
                        await dm.send(embed=discord.Embed(description="❌ Invalid channel ID.", color=ERROR_COLOR))
                        continue
                    break
                except ValueError:
                    await dm.send(embed=discord.Embed(description="❌ Invalid channel ID.", color=ERROR_COLOR))

            # Step 2: Mode
            while True:
                mode_input = await self.ask_input(dm, user, "Mode", "Do you want messages to be `text` or `embed`?", show_back=True)
                mode = mode_input.lower()
                if mode not in ("text", "embed"):
                    await dm.send(embed=discord.Embed(description="❌ Invalid mode. Choose `text` or `embed`.", color=ERROR_COLOR))
                    continue
                break

            data = {"channel_id": channel_id, "mode": mode}

            # Steps based on mode
            steps = []
            if mode == "text":
                steps = [
                    {"name": "Text Message", "key": "text", "prompt": "Enter the text message.", "allow_skip": True, "placeholders": "{mention}, {user}, {server}, {count}", "image": False},
                    {"name": "Text Image", "key": "image_url", "prompt": "Upload or paste an image URL.", "allow_skip": True, "placeholders": "{member_pfp}, {server_icon}", "image": True},
                ]
            else:  # embed
                steps = [
                    {"name": "Embed Title", "key": "title", "prompt": "Embed title", "allow_skip": True, "placeholders": "{mention}, {user}, {server}, {count}", "image": False},
                    {"name": "Embed Description", "key": "description", "prompt": "Embed description", "allow_skip": True, "placeholders": "{mention}, {user}, {server}, {count}", "image": False},
                    {"name": "Embed Color", "key": "color", "prompt": "Embed color HEX (e.g., #00ff00)", "allow_skip": True, "placeholders": None, "image": False},
                    {"name": "Embed Image", "key": "image_url", "prompt": "Embed image URL", "allow_skip": True, "placeholders": "{member_pfp}, {server_icon}", "image": True},
                    {"name": "Embed Thumbnail", "key": "thumbnail_url", "prompt": "Embed thumbnail URL", "allow_skip": True, "placeholders": "{member_pfp}, {server_icon}", "image": True},
                    {"name": "Embed Author Icon", "key": "icon_url", "prompt": "Embed author icon URL", "allow_skip": True, "placeholders": "{member_pfp}, {server_icon}", "image": True},
                    {"name": "Embed Footer Text", "key": "footer_text", "prompt": "Embed footer text", "allow_skip": True, "placeholders": "{mention}, {user}, {server}, {count}", "image": False},
                    {"name": "Embed Footer Icon", "key": "footer_icon", "prompt": "Embed footer icon URL", "allow_skip": True, "placeholders": "{member_pfp}, {server_icon}", "image": True},
                ]

            index = 0
            while index < len(steps):
                step = steps[index]
                allow_skip = step.get("allow_skip", False)
                placeholders = step.get("placeholders")
                image = step.get("image", False)
                show_back = index > 0  # Back works from second step onward

                answer = await self.ask_input(dm, user, step["name"], step["prompt"], allow_skip=allow_skip, placeholders=placeholders, image=image, show_back=show_back)

                if answer == "back":
                    if index > 0:
                        index -= 1
                        continue
                    else:
                        await dm.send(embed=discord.Embed(description="❌ Cannot go back from this step.", color=ERROR_COLOR))
                        continue

                if step["key"] == "color" and answer:
                    color_val = answer.replace("#", "0x") if answer.startswith("#") else answer
                    try:
                        int(color_val, 16)
                        answer = color_val
                    except ValueError:
                        await dm.send(embed=discord.Embed(description="❌ Invalid HEX color.", color=ERROR_COLOR))
                        continue

                data[step["key"]] = answer
                index += 1

            # Save configuration
            cfg = load_config()
            gid = str(guild.id)
            cfg.setdefault(gid, {})
            cfg[gid][event_type] = data
            save_config(cfg)

            await dm.send(embed=discord.Embed(
                description=f"✅ Setup complete for **{event_type}** messages in <#{data['channel_id']}>!",
                color=SUCCESS_COLOR
            ))

        except discord.Forbidden:
            try:
                await user.send("❌ I couldn't DM you. Please enable DMs and try again.")
            except:
                pass

async def setup(bot):
    await bot.add_cog(WelcomeLeave(bot))