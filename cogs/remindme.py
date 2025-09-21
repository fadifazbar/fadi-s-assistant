import discord
from discord.ext import commands, tasks
from discord import ui
import asyncio, os, json, re
from datetime import datetime

DATA_FILE = "/data/reminders.json"

# ======================
# Data Helpers
# ======================
def load_reminders():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    with open(DATA_FILE, "w") as f:
        json.dump(reminders, f)

# ======================
# Time Parser
# ======================
def parse_time(timestr: str | None):
    if not timestr:
        return 0  # instant reminder

    units = {
        "s": 1, "sec": 1, "second": 1,
        "m": 60, "min": 60, "minute": 60,
        "h": 3600, "hr": 3600, "hour": 3600,
        "d": 86400, "day": 86400,
        "w": 604800, "week": 604800,
        "mon": 2592000, "month": 2592000,
    }

    pattern = r"(\d+)([a-zA-Z]+)"
    matches = re.findall(pattern, timestr.strip().lower())
    if not matches:
        return None

    total = 0
    for value, unit in matches:
        if unit not in units:
            return None
        total += int(value) * units[unit]

    return total

# ======================
# Cog
# ======================
class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = load_reminders()
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    # background checker for reminders
    @tasks.loop(seconds=10)
    async def check_reminders(self):
        now = datetime.utcnow().timestamp()
        to_run = [r for r in self.reminders if r["time"] <= now]
        for reminder in to_run:
            user = self.bot.get_user(reminder["user"])
            if user:
                try:
                    await user.send(f"⏰ Reminder: **{reminder['message']}**")
                except discord.Forbidden:
                    pass
            self.reminders.remove(reminder)
        if to_run:
            save_reminders(self.reminders)

    async def reminder_task(self, reminder, seconds):
        await asyncio.sleep(seconds)
        user = self.bot.get_user(reminder["user"])
        if user:
            try:
                await user.send(f"⏰ Reminder: **{reminder['message']}**")
            except discord.Forbidden:
                pass
        if reminder in self.reminders:
            self.reminders.remove(reminder)
            save_reminders(self.reminders)

    # ======================
    # $remindme
    # ======================
    @commands.command(name="remindme")
    async def remindme_prefix(self, ctx, when: str = None, *, message: str):
        seconds = parse_time(when)
        if seconds is None:
            return await ctx.send("❌ Invalid time format. Example: `10m`, `1h30min`, `2week`, `1mon`")

        end_time = int(datetime.utcnow().timestamp() + seconds)
        reminder = {"user": ctx.author.id, "message": message, "time": end_time}
        self.reminders.append(reminder)
        save_reminders(self.reminders)

        # instant reminder
        if seconds == 0:
            await ctx.author.send(f"⏰ Reminder: **{message}**")
            self.reminders.remove(reminder)
            save_reminders(self.reminders)
            return await ctx.send(f"✅ Sent your instant reminder: **{message}**")

        self.bot.loop.create_task(self.reminder_task(reminder, seconds))

        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=f"**Message:** {message}\n**Time:** <t:{end_time}:R>",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)

    # ======================
    # $reminders
    # ======================
    @commands.command(name="reminders")
    async def reminders_list(self, ctx):
        user_reminders = [r for r in self.reminders if r["user"] == ctx.author.id]
        if not user_reminders:
            return await ctx.send("📭 You have no active reminders.")

        page = 0
        per_page = 5

        def make_embed(page):
            embed = discord.Embed(
                title=f"📝 Your Reminders (Page {page+1}/{(len(user_reminders)-1)//per_page+1})",
                color=discord.Color.blue()
            )
            start = page * per_page
            end = start + per_page
            for idx, r in enumerate(user_reminders[start:end], start=1):
                embed.add_field(
                    name=f"{idx+start}. {r['message']}",
                    value=f"⏰ <t:{r['time']}:R>",
                    inline=False
                )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            return embed

        class ReminderView(ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary)
            async def back(self, interaction, button):
                nonlocal page
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                if page > 0:
                    page -= 1
                    await interaction.response.edit_message(embed=make_embed(page), view=self)

            @ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            async def forward(self, interaction, button):
                nonlocal page
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                if (page+1) * per_page < len(user_reminders):
                    page += 1
                    await interaction.response.edit_message(embed=make_embed(page), view=self)

        await ctx.send(embed=make_embed(page), view=ReminderView())

    # ======================
    # $cancelreminder
    # ======================
    @commands.command(name="cancelreminder", aliases=["cr", "rcancel"])
    async def cancel_reminder(self, ctx):
        user_reminders = [r for r in self.reminders if r["user"] == ctx.author.id]
        if not user_reminders:
            return await ctx.send("📭 You have no active reminders to cancel.")

        options = [
            discord.SelectOption(
                label=r["message"][:50],
                description=f"Reminds <t:{r['time']}:R>",
                value=str(idx)
            )
            for idx, r in enumerate(user_reminders)
        ]

        class CancelView(ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @ui.select(placeholder="Select a reminder to cancel", options=options)
            async def select_callback(self, interaction, select):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                idx = int(select.values[0])
                reminder = user_reminders[idx]

                confirm_view = ui.View()

                @ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
                async def confirm(btnself, inter, button):
                    if inter.user != ctx.author:
                        return await inter.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                    self.reminders.remove(reminder)
                    save_reminders(self.reminders)
                    await inter.response.edit_message(content=f"🗑️ Reminder cancelled: **{reminder['message']}**", embed=None, view=None)

                @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(btnself, inter, button):
                    if inter.user != ctx.author:
                        return await inter.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                    await inter.response.edit_message(content="❎ Cancel action aborted.", embed=None, view=None)

                await interaction.response.edit_message(
                    content=f"⚠️ Do you really want to cancel **{reminder['message']}**?",
                    view=confirm_view
                )

        await ctx.send("📋 Select a reminder to cancel:", view=CancelView())

# ======================
# Setup
# ======================
async def setup(bot):
    await bot.add_cog(ReminderCog(bot))