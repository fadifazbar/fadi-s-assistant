import discord from discord.ext import commands from discord import app_commands, ui import os, json, datetime

DATA_FILE = "/data/logs.json" BOT_NAME = "Fadi's Assistant"

=========================

Data Helpers

=========================

def load_config(): if os.path.exists(DATA_FILE): with open(DATA_FILE, "r") as f: return json.load(f) return {}

def save_config(config): with open(DATA_FILE, "w") as f: json.dump(config, f, indent=2)

=========================

Webhook Helper

=========================

async def send_log(guild: discord.Guild, category: str, embed: discord.Embed): config = load_config() gid = str(guild.id) if gid not in config or category not in config[gid]: return

webhook_url = config[gid][category]
try:
    wh = discord.Webhook.from_url(webhook_url, client=guild._state.http)
    await wh.send(embed=embed, username=BOT_NAME)
except Exception:
    pass

=========================

Cog

=========================

class LoggingCog(commands.Cog): def init(self, bot): self.bot = bot

# =========================
# Setup Command with Select
# =========================
@app_commands.command(name="setlogs", description="Setup logging categories with dropdown")
async def setlogs(self, interaction: discord.Interaction):
    categories = {
        "messages": "Message Updates (delete/edit/pin)",
        "roles": "Role Updates (create/delete/rename/recolor)",
        "members": "Member Updates (ban/kick/mute/unmute/unban/nickname)",
        "joins": "Member Joining (join/leave)",
        "threads": "Threads (create/edit/delete)",
        "voice": "Voice Events (connect/disconnect/move/mute/deafen)",
        "channels": "Channels (create/delete/rename)",
        "server": "Server Updates (name/icon/banner)",
    }

    options = [discord.SelectOption(label=name, description=desc, value=key) for key, desc in categories.items()]

    class SetupView(ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @ui.select(placeholder="Choose a category to setup", options=options)
        async def select_callback(self, interaction2: discord.Interaction, select):
            category = select.values[0]

            class ChannelSelect(ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.add_item(ui.ChannelSelect(placeholder="Select a channel", channel_types=[discord.ChannelType.text]))

                @ui.select()
                async def channel_selected(self, inner_interaction: discord.Interaction, channel_select):
                    channel = channel_select.values[0]
                    webhook = await channel.create_webhook(name=BOT_NAME)

                    config = load_config()
                    gid = str(interaction.guild.id)
                    if gid not in config:
                        config[gid] = {}
                    config[gid][category] = webhook.url
                    save_config(config)

                    await inner_interaction.response.send_message(f"✅ {categories[category]} will log to {channel.mention}", ephemeral=True)

            await interaction2.response.send_message("Now select the channel:", view=ChannelSelect(), ephemeral=True)

    await interaction.response.send_message("Select a logging category to configure:", view=SetupView(), ephemeral=True)

# =========================
# Listeners - Messages
# =========================
@commands.Cog.listener()
async def on_message_delete(self, message: discord.Message):
    if message.author.bot:
        return
    embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Author", value=f"{message.author} ({message.author.id})")
    embed.add_field(name="Channel", value=message.channel.mention)
    embed.add_field(name="Content", value=message.content or "*(embed/attachment)*", inline=False)
    embed.set_footer(text=f"Message ID: {message.id}")
    await send_log(message.guild, "messages", embed)

@commands.Cog.listener()
async def on_message_edit(self, before: discord.Message, after: discord.Message):
    if before.author.bot or before.content == after.content:
        return
    embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Author", value=f"{before.author} ({before.author.id})")
    embed.add_field(name="Channel", value=before.channel.mention)
    embed.add_field(name="Before", value=before.content or "*(embed/attachment)*", inline=False)
    embed.add_field(name="After", value=after.content or "*(embed/attachment)*", inline=False)
    embed.set_footer(text=f"Message ID: {before.id}")
    await send_log(before.guild, "messages", embed)

# =========================
# Listeners - Members
# =========================
@commands.Cog.listener()
async def on_member_join(self, member: discord.Member):
    embed = discord.Embed(title="👋 Member Joined", description=f"{member.mention} ({member.id})", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    await send_log(member.guild, "joins", embed)

@commands.Cog.listener()
async def on_member_remove(self, member: discord.Member):
    embed = discord.Embed(title="🚪 Member Left", description=f"{member} ({member.id})", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
    await send_log(member.guild, "joins", embed)

# =========================
# Listeners - Channels
# =========================
@commands.Cog.listener()
async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
    embed = discord.Embed(title="📺 Channel Created", description=f"{channel.mention} ({channel.id})", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
    await send_log(channel.guild, "channels", embed)

@commands.Cog.listener()
async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
    embed = discord.Embed(title="❌ Channel Deleted", description=f"{channel.name} ({channel.id})", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
    await send_log(channel.guild, "channels", embed)

@commands.Cog.listener()
async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    if before.name != after.name:
        embed = discord.Embed(title="✏️ Channel Renamed", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Old Name", value=before.name)
        embed.add_field(name="New Name", value=after.name)
        await send_log(after.guild, "channels", embed)

# =========================
# TODO: Add role, server, threads, voice logs with old/new values and audit log info
# =========================

=========================

Setup

=========================

async def setup(bot): await bot.add_cog(LoggingCog(bot))

