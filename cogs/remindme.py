import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import asyncio
import os, json, re
from datetime import datetime, timedelta

DATA_FILE = "/data/reminders.json"

def load_reminders():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ reminders.json corrupted, resetting file...")
            return []
    return []

def save_reminders(reminders):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(reminders, f, indent=2)
    print(f"💾 Saved {len(reminders)} reminders to {DATA_FILE}")

# ======================
# Time Parser
# ======================
def parse_time(timestr: str | None):
    if not timestr:
        return 0

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
        self.active_loops = {}  # user_id -> asyncio.Task
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    # ======================
    # Background checker
    # ======================
    @tasks.loop(seconds=10)
    async def check_reminders(self):
        now = datetime.utcnow().timestamp()
        to_run = [r for r in self.reminders if r["time"] <= now]
        for reminder in to_run:
            user = self.bot.get_user(reminder["user"])
            if user:
                await self.start_reminder_loop(user, reminder)
            if reminder in self.reminders:
                self.reminders.remove(reminder)
        if to_run:
            save_reminders(self.reminders)

    async def start_reminder_loop(self, user: discord.User, reminder: dict):
        msg = f"⏰ Reminder: **{reminder['message']}**\nReply with `Remind` to stop the reminding.\n**You will be reminded again after 5 minutes."

        async def loop_func():
            while True:
                try:
                    await user.send(msg)
                except discord.Forbidden:
                    break
                await asyncio.sleep(5)  # 5 minutes

        task = asyncio.create_task(loop_func())
        self.active_loops[user.id] = task

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.DMChannel):
            return
        if message.author.bot:
            return

        if message.content.strip().lower() == "remind":
            if message.author.id in self.active_loops:
                self.active_loops[message.author.id].cancel()
                del self.active_loops[message.author.id]
                await message.channel.send("✅ Successfully stopped the reminding.")

    # ======================
    # Commands
    # ======================
    @commands.command(name="remindme")
    async def remindme_prefix(self, ctx, when: str = None, *, message: str = None):
        await self.create_reminder(ctx, ctx.author, when, message)

    @app_commands.command(name="remindme", description="Set a reminder")
    async def remindme_slash(self, interaction: discord.Interaction, when: str, message: str):
        await self.create_reminder(interaction, interaction.user, when, message)

    async def create_reminder(self, src, user, when, message):
        seconds = parse_time(when)
        if seconds is None:
            err = "❌ Invalid time format. Example: `10m`, `1h30min`, `2week`, `1mon`"
            return await (src.response.send_message(err) if isinstance(src, discord.Interaction) else src.send(err))

        end_time = int(datetime.utcnow().timestamp() + seconds)
        reminder = {"user": user.id, "message": message, "time": end_time}
        self.reminders.append(reminder)
        save_reminders(self.reminders)

        abs_time = datetime.utcfromtimestamp(end_time).strftime("%d %B %Y, %H:%M UTC")
        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=f"**Message:** {message}\n**Relative:** <t:{end_time}:R>\n**Exact:** {abs_time}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Requested by {user}", icon_url=user.avatar.url if user.avatar else None)

        if seconds == 0:
            await self.start_reminder_loop(user, reminder)
            self.reminders.remove(reminder)
            save_reminders(self.reminders)

        if isinstance(src, discord.Interaction):
            await src.response.send_message(embed=embed)
        else:
            await src.send(embed=embed)

    # ======================
    # reminders list
    # ======================
    @commands.command(name="reminders")
    async def reminders_prefix(self, ctx):
        await self.send_reminders_list(ctx, ctx.author)

    @app_commands.command(name="reminders", description="Show your active reminders")
    async def reminders_slash(self, interaction: discord.Interaction):
        await self.send_reminders_list(interaction, interaction.user)

    async def send_reminders_list(self, src, user):
        user_reminders = [r for r in self.reminders if r["user"] == user.id]
        if not user_reminders:
            msg = "📭 You have no active reminders."
            return await (src.response.send_message(msg) if isinstance(src, discord.Interaction) else src.send(msg))

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
                abs_time = datetime.utcfromtimestamp(r["time"]).strftime("%d %B %Y, %H:%M UTC")
                embed.add_field(
                    name=f"{idx+start}. {r['message']}",
                    value=f"⏰ <t:{r['time']}:R> ({abs_time})",
                    inline=False
                )
            embed.set_footer(text=f"Requested by {user}", icon_url=user.avatar.url if user.avatar else None)
            return embed

        class ReminderView(ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary)
            async def back(self, interaction, button):
                nonlocal page
                if interaction.user != user:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                if page > 0:
                    page -= 1
                    await interaction.response.edit_message(embed=make_embed(page), view=self)

            @ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            async def forward(self, interaction, button):
                nonlocal page
                if interaction.user != user:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                if (page+1) * per_page < len(user_reminders):
                    page += 1
                    await interaction.response.edit_message(embed=make_embed(page), view=self)

        if isinstance(src, discord.Interaction):
            await src.response.send_message(embed=make_embed(page), view=ReminderView())
        else:
            await src.send(embed=make_embed(page), view=ReminderView())

    # ======================
    # cancel reminder
    # ======================
    @commands.command(name="cancelreminder", aliases=["cr", "rcancel"])
    async def cancel_prefix(self, ctx):
        await self.cancel_reminder(ctx, ctx.author)

    @app_commands.command(name="cancelreminder", description="Cancel a reminder")
    async def cancel_slash(self, interaction: discord.Interaction):
        await self.cancel_reminder(interaction, interaction.user)

    async def cancel_reminder(self, src, user):
        user_reminders = [r for r in self.reminders if r["user"] == user.id]
        if not user_reminders:
            msg = "📭 You have no active reminders to cancel."
            return await (src.response.send_message(msg) if isinstance(src, discord.Interaction) else src.send(msg))

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
                if interaction.user != user:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                idx = int(select.values[0])
                reminder = user_reminders[idx]

                confirm_view = ui.View()

                @ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
                async def confirm(btnself, inter, button):
                    if inter.user != user:
                        return await inter.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                    self.reminders.remove(reminder)
                    save_reminders(self.reminders)
                    await inter.response.edit_message(
                        content=f"🗑️ Reminder cancelled: **{reminder['message']}**",
                        embed=None,
                        view=None
                    )

                @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(btnself, inter, button):
                    if inter.user != user:
                        return await inter.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                    await inter.response.edit_message(content="❎ Cancel action aborted.", embed=None, view=None)

                await interaction.response.edit_message(
                    content=f"⚠️ Do you really want to cancel **{reminder['message']}**?",
                    view=confirm_view
                )

        if isinstance(src, discord.Interaction):
            await src.response.send_message("📋 Select a reminder to cancel:", view=CancelView())
        else:
            await src.send("📋 Select a reminder to cancel:", view=CancelView())


# ======================
# Setup
# ======================
async def setup(bot):
    await bot.add_cog(ReminderCog(bot))