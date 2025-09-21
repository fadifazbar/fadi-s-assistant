import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import json
import os
from datetime import datetime, timedelta

DATA_FILE = "/data/reminders.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)

def load_reminders():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_reminders(reminders):
    with open(DATA_FILE, "w") as f:
        json.dump(reminders, f)

def parse_time(timestr: str):
    unit = timestr[-1]
    num = int(timestr[:-1])
    if unit == "s":
        return num
    elif unit == "m":
        return num * 60
    elif unit == "h":
        return num * 3600
    elif unit == "d":
        return num * 86400
    else:
        return None

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = load_reminders()
        self.bot.loop.create_task(self.resume_reminders())

    async def resume_reminders(self):
        await self.bot.wait_until_ready()
        now = datetime.utcnow().timestamp()
        for reminder in self.reminders.copy():
            remaining = reminder["time"] - now
            if remaining > 0:
                self.bot.loop.create_task(self.reminder_task(reminder, remaining))
            else:
                user = self.bot.get_user(reminder["user"])
                if user:
                    await user.send(f"⏰ Reminder: {reminder['message']}")
                self.reminders.remove(reminder)
        save_reminders(self.reminders)

    async def reminder_task(self, reminder, delay):
        await asyncio.sleep(delay)
        user = self.bot.get_user(reminder["user"])
        if user:
            await user.send(f"⏰ Reminder: {reminder['message']}")
        if reminder in self.reminders:
            self.reminders.remove(reminder)
            save_reminders(self.reminders)

    # ----- PREFIX REMINDME -----
    @commands.command(name="remindme")
    async def remindme_prefix(self, ctx, when: str, *, message: str):
        seconds = parse_time(when)
        if not seconds:
            return await ctx.send("❌ Invalid time format. Use s/m/h/d")
        end_time = datetime.utcnow().timestamp() + seconds
        reminder = {"user": ctx.author.id, "message": message, "time": end_time}
        self.reminders.append(reminder)
        save_reminders(self.reminders)
        self.bot.loop.create_task(self.reminder_task(reminder, seconds))
        await ctx.send(f"✅ I will remind you in {when}: **{message}**")

    # ----- SLASH REMINDME -----
    @app_commands.command(name="remindme", description="Set a reminder")
    async def remindme_slash(self, interaction: discord.Interaction, when: str, message: str):
        seconds = parse_time(when)
        if not seconds:
            return await interaction.response.send_message("❌ Invalid time format. Use s/m/h/d", ephemeral=True)
        end_time = datetime.utcnow().timestamp() + seconds
        reminder = {"user": interaction.user.id, "message": message, "time": end_time}
        self.reminders.append(reminder)
        save_reminders(self.reminders)
        self.bot.loop.create_task(self.reminder_task(reminder, seconds))
        await interaction.response.send_message(f"✅ I will remind you in {when}: **{message}**")

    # ----- LIST REMINDERS -----
    @commands.command(name="listreminders")
    async def listreminders(self, ctx):
        user_reminders = [r for r in self.reminders if r["user"] == ctx.author.id]
        if not user_reminders:
            return await ctx.send("📭 You have no active reminders!")

        page = 0
        per_page = 5

        def make_embed(page):
            embed = discord.Embed(
                title=f"📝 Your Reminders (Page {page+1}/{(len(user_reminders)-1)//per_page+1})",
                color=discord.Color.blurple()
            )
            start = page * per_page
            end = start + per_page
            for i, r in enumerate(user_reminders[start:end], start=start+1):
                remaining = int(r["time"] - datetime.utcnow().timestamp())
                mins, secs = divmod(remaining, 60)
                hours, mins = divmod(mins, 60)
                embed.add_field(
                    name=f"{i}. ⏰ {r['message']}",
                    value=f"Expires in {hours}h {mins}m {secs}s",
                    inline=False
                )
            return embed

        message = await ctx.send(embed=make_embed(page))
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == message.id

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                if str(reaction.emoji) == "➡️" and (page+1)*per_page < len(user_reminders):
                    page += 1
                    await message.edit(embed=make_embed(page))
                elif str(reaction.emoji) == "⬅️" and page > 0:
                    page -= 1
                    await message.edit(embed=make_embed(page))
                await message.remove_reaction(reaction, user)
            except asyncio.TimeoutError:
                break

    # ----- CANCEL REMINDER -----
    @commands.command(name="cancelreminder")
    async def cancelreminder(self, ctx):
        user_reminders = [r for r in self.reminders if r["user"] == ctx.author.id]
        if not user_reminders:
            return await ctx.send("📭 You have no active reminders!")

        options = [
            discord.SelectOption(label=r["message"], description="Your reminder", value=str(i))
            for i, r in enumerate(user_reminders)
        ]

        class ReminderSelect(ui.View):
            @ui.select(placeholder="Select a reminder to cancel ❌", options=options)
            async def select_callback(self, interaction: discord.Interaction, select: ui.Select):
                idx = int(select.values[0])
                removed = user_reminders[idx]
                self.cog.reminders.remove(removed)
                save_reminders(self.cog.reminders)
                await interaction.response.edit_message(content=f"✅ Reminder **{removed['message']}** has been cancelled!", embed=None, view=None)

            def __init__(self, cog):
                super().__init__(timeout=30)
                self.cog = cog

        embed = discord.Embed(title="❌ Cancel a Reminder", description="Choose one of your reminders below:", color=discord.Color.red())
        await ctx.send(embed=embed, view=ReminderSelect(self))

async def setup(bot):
    await bot.add_cog(Reminder(bot))