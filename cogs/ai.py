import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import openai
import time

# ==========================
# CONFIG
# ==========================
openai.api_key = os.getenv("OPENAI_API_KEY")  # Railway secret
MEMORY_FILE = "chat_memory.json"
IMPORTANT_MEMORY_DURATION = 3 * 60 * 60  # 3 hours

# ==========================
# MEMORY HANDLING
# ==========================
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump({}, f)

def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def cleanup_important_memories(guild_data):
    """Remove expired important memories."""
    now = time.time()
    if "important" not in guild_data:
        guild_data["important"] = []
    guild_data["important"] = [
        mem for mem in guild_data["important"]
        if now - mem["time"] < IMPORTANT_MEMORY_DURATION
    ]
    return guild_data


# ==========================
# COG
# ==========================
class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================
    # PREFIX COMMANDS
    # ================
    @commands.command(name="enablechat")
    async def enable_chat_prefix(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            return
        data = load_memory()
        data[str(ctx.guild.id)] = {
            "enabled": True,
            "history": [],
            "important": []
        }
        save_memory(data)
        await ctx.send("✅ AI chat enabled in this server!")

    @commands.command(name="disablechat")
    async def disable_chat_prefix(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            return
        data = load_memory()
        if str(ctx.guild.id) in data:
            data[str(ctx.guild.id)]["enabled"] = False
            save_memory(data)
        await ctx.send("❌ AI chat disabled in this server!")

    @commands.command(name="clearchat")
    async def clear_chat_prefix(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            return
        data = load_memory()
        if str(ctx.guild.id) in data:
            data[str(ctx.guild.id)]["history"] = []
            data[str(ctx.guild.id)]["important"] = []
            save_memory(data)
        await ctx.send("🧹 AI memory has been cleared for this server!")

    # ================
    # SLASH COMMANDS
    # ================
    @app_commands.command(name="enablechat", description="Enable AI chat in this server")
    async def enable_chat_slash(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.DMChannel):
            return
        data = load_memory()
        data[str(interaction.guild.id)] = {
            "enabled": True,
            "history": [],
            "important": []
        }
        save_memory(data)
        await interaction.response.send_message("✅ AI chat enabled in this server!")

    @app_commands.command(name="disablechat", description="Disable AI chat in this server")
    async def disable_chat_slash(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.DMChannel):
            return
        data = load_memory()
        if str(interaction.guild.id) in data:
            data[str(interaction.guild.id)]["enabled"] = False
            save_memory(data)
        await interaction.response.send_message("❌ AI chat disabled in this server!")

    @app_commands.command(name="clearchat", description="Clear AI memory in this server")
    async def clear_chat_slash(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.DMChannel):
            return
        data = load_memory()
        if str(interaction.guild.id) in data:
            data[str(interaction.guild.id)]["history"] = []
            data[str(interaction.guild.id)]["important"] = []
            save_memory(data)
        await interaction.response.send_message("🧹 AI memory has been cleared for this server!")

    # ================
    # GUILD JOIN
    # ================
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Automatically disable AI when bot joins a new guild."""
        data = load_memory()
        data[str(guild.id)] = {
            "enabled": False,
            "history": [],
            "important": []
        }
        save_memory(data)

    # ================
    # MESSAGE HANDLER
    # ================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if isinstance(message.channel, discord.DMChannel):
            return

        data = load_memory()
        guild_id = str(message.guild.id)

        if guild_id not in data or not data[guild_id].get("enabled", False):
            return  # chat disabled

        # Clean expired memories
        data[guild_id] = cleanup_important_memories(data[guild_id])

        # Respond if bot is mentioned, reply, or just chatting
        should_respond = False
        if self.bot.user.mentioned_in(message):
            should_respond = True
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            should_respond = True
        if not should_respond:
            should_respond = True  # always respond in chat mode

        if not should_respond:
            return

        # "remember that ..." handler
        if message.content.lower().startswith("remember that"):
            memory_text = message.content[len("remember that"):].strip()
            if memory_text:
                data[guild_id]["important"].append({
                    "content": memory_text,
                    "time": time.time()
                })
                save_memory(data)
                await message.channel.send("📝 Got it! I'll remember that for a while.")
                return

        # Prepare history
        history = data[guild_id]["history"]
        history.append({"role": "user", "content": f"{message.author.display_name}: {message.content}"})
        history = history[-20:]  # keep last 20 messages
        data[guild_id]["history"] = history
        save_memory(data)

        # Add important context
        important_context = [
            {"role": "system", "content": f"Remember this: {mem['content']}"}
            for mem in data[guild_id]["important"]
        ]

        # AI response
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful and friendly AI chatbot that talks with everyone in a Discord server."}
                ] + important_context + history
            )
            reply = response["choices"][0]["message"]["content"]
        except Exception as e:
            reply = f"⚠️ Error generating response: {e}"

        # Truncate at 1900 chars
        if len(reply) > 1900:
            reply = reply[:1900]

        # Save bot reply
        history.append({"role": "assistant", "content": reply})
        data[guild_id]["history"] = history
        save_memory(data)

        await message.channel.send(reply)


# ==========================
# SETUP
# ==========================
async def setup(bot: commands.Bot):
    await bot.add_cog(AIChat(bot))