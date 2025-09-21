# cogs/remindme.py
import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import asyncio
import os, json, re
from datetime import datetime
import uuid

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
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(reminders, f, indent=2)
        print(f"💾 Saved {len(reminders)} reminders to {DATA_FILE}")
    except Exception as e:
        print(f"❌ Failed to save reminders: {e}")


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
        # start checker loop
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()
        # cancel any running tasks
        for t in list(self.active_loops.values()):
            try:
                t.cancel()
            except Exception:
                pass
        self.active_loops.clear()

    @commands.Cog.listener()
    async def on_ready(self):
        # Restart active reminders after bot restarts
        for reminder in self.reminders:
            if reminder.get("active", True) and reminder["time"] <= datetime.utcnow().timestamp():
                user = self.bot.get_user(reminder["user"])
                if user:
                    # avoid duplicate loops if one exists
                    if user.id not in self.active_loops:
                        await self.start_reminder_loop(user, reminder)

    # ======================
    # Background checker
    # ======================
    @tasks.loop(seconds=10)
    async def check_reminders(self):
        now = datetime.utcnow().timestamp()
        to_run = [r for r in self.reminders if r["time"] <= now and r.get("active", True)]
        started_any = False
        for reminder in to_run:
            user = self.bot.get_user(reminder["user"])
            if user:
                if user.id not in self.active_loops:
                    # mark active (if not already) and start loop
                    reminder["active"] = True
                    await self.start_reminder_loop(user, reminder)
                    started_any = True
        if started_any:
            save_reminders(self.reminders)

    async def start_reminder_loop(self, user: discord.User, reminder: dict):
        # ensure it's active
        if not reminder.get("active", True):
            return

        # Prevent duplicate loops
        if user.id in self.active_loops:
            return

        msg = (
            f"⏰ Reminder: **{reminder['message']}**\n"
            f"Reply with `Remind` to stop the reminding.\n"
            f"**You will be reminded again after 5 minutes.**"
        )

        async def loop_func():
            try:
                while reminder.get("active", True):
                    try:
                        await user.send(msg)
                    except discord.Forbidden:
                        # can't DM the user anymore — mark inactive and stop
                        reminder["active"] = False
                        save_reminders(self.reminders)
                        break
                    # sleep 5 minutes
                    await asyncio.sleep(300)
            except asyncio.CancelledError:
                # loop cancelled (user stopped reminders or bot shutting down)
                pass
            finally:
                # cleanup active_loops entry if exists
                if user.id in self.active_loops:
                    del self.active_loops[user.id]

        # create task and store it
        task = asyncio.create_task(loop_func())
        self.active_loops[user.id] = task
        # ensure persistence reflects active state
        reminder["active"] = True
        save_reminders(self.reminders)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.DMChannel):
            return
        if message.author.bot:
            return

        if message.content.strip().lower() == "remind":
            # Stop the user's active loop
            if message.author.id in self.active_loops:
                try:
                    self.active_loops[message.author.id].cancel()
                except Exception:
                    pass
                del self.active_loops[message.author.id]

            # Only deactivate the first triggered reminder
            now = datetime.utcnow().timestamp()
            for reminder in self.reminders:
                if (
                    reminder["user"] == message.author.id
                    and reminder.get("active", True)
                    and reminder["time"] <= now  # already started firing
                ):
                    reminder["active"] = False
                    save_reminders(self.reminders)
                    break  # stop after deactivating one

            await message.channel.send("✅ Successfully stopped the current reminder.")

# ======================
# Commands
# ======================
class RemindMe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = []
        self.active_loops = {}

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
        reminder_id = str(uuid.uuid4())  # ✅ unique ID per reminder

        reminder = {
            "id": reminder_id,
            "user": user.id,
            "message": message,
            "time": end_time,
            "active": True,
            "repeat": True
        }
        self.reminders.append(reminder)
        save_reminders(self.reminders)

        # Start this reminder loop
        self.start_reminder_loop(reminder)

        abs_time = datetime.utcfromtimestamp(end_time).strftime("%d %B %Y, %H:%M UTC")
        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=f"**Message:** {message}\n**Relative:** <t:{int(end_time)}:R>\n**Exact:** {abs_time}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Requested by {user}", icon_url=user.avatar.url if user.avatar else None)

        class CancelNow(ui.View):
            def __init__(self, cog, reminder):
                super().__init__(timeout=60)
                self.cog = cog
                self.reminder = reminder

            @ui.button(label="❌ Cancel Reminder", style=discord.ButtonStyle.danger)
            async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
                if interaction.user != user:
                    return await interaction.response.send_message("❌ This isn’t your reminder!", ephemeral=True)
                self.reminder["active"] = False
                save_reminders(self.cog.reminders)
                if user.id in self.cog.active_loops and self.reminder["id"] in self.cog.active_loops[user.id]:
                    try:
                        self.cog.active_loops[user.id][self.reminder["id"]].cancel()
                    except Exception:
                        pass
                    del self.cog.active_loops[user.id][self.reminder["id"]]
                await interaction.response.edit_message(
                    content=f"🗑️ Reminder cancelled: **{self.reminder['message']}**",
                    embed=None,
                    view=None
                )

        if isinstance(src, discord.Interaction):
            await src.response.send_message(embed=embed, view=CancelNow(self, reminder))
        else:
            await src.send(embed=embed, view=CancelNow(self, reminder))

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
        user_reminders = [r for r in self.reminders if r["user"] == user.id and r.get("active", True)]
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
                abs_time = datetime.utcfromtimestamp(int(r["time"])).strftime("%d %B %Y, %H:%M UTC")
                embed.add_field(
                    name=f"{idx+start}. {r['message']}",
                    value=f"⏰ <t:{int(r['time'])}:R> ({abs_time})",
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
    # cancel reminder (list)
    # ======================
    @commands.command(name="cancelreminder", aliases=["cr", "rcancel"])
    async def cancel_prefix(self, ctx):
        await self.cancel_reminder(ctx, ctx.author)

    @app_commands.command(name="cancelreminder", description="Cancel a reminder")
    async def cancel_slash(self, interaction: discord.Interaction):
        await self.cancel_reminder(interaction, interaction.user)

    async def cancel_reminder(self, src, user):
        user_reminders = [r for r in self.reminders if r["user"] == user.id and r.get("active", True)]
        if not user_reminders:
            msg = "📭 You have no active reminders to cancel."
            return await (src.response.send_message(msg) if isinstance(src, discord.Interaction) else src.send(msg))

        options = [
            discord.SelectOption(
                label=r["message"][:50],
                description=f"Reminds <t:{int(r['time'])}:R>",
                value=str(idx)
            )
            for idx, r in enumerate(user_reminders)
        ]

        class CancelView(ui.View):
            def __init__(self, cog):
                super().__init__(timeout=60)
                self.cog = cog

            @ui.select(placeholder="Select a reminder to cancel", options=options)
            async def select_callback(self, interaction: discord.Interaction, select: ui.Select):
                if interaction.user != user:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                idx = int(select.values[0])
                reminder = user_reminders[idx]

                confirm_view = ConfirmCancel(reminder, user, self.cog)

                await interaction.response.edit_message(
                    content=f"⚠️ Do you really want to cancel **{reminder['message']}**?",
                    view=confirm_view
                )

        class ConfirmCancel(ui.View):
            def __init__(self, reminder, user, cog):
                super().__init__(timeout=60)
                self.reminder = reminder
                self.user = user
                self.cog = cog

            @ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: ui.Button):
                if interaction.user != self.user:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                # mark inactive
                self.reminder["active"] = False
                # cancel any active loop for that user
                if self.reminder["user"] in self.cog.active_loops:
                    try:
                        self.cog.active_loops[self.reminder["user"]].cancel()
                    except Exception:
                        pass
                    del self.cog.active_loops[self.reminder["user"]]
                save_reminders(self.cog.reminders)
                await interaction.response.edit_message(
                    content=f"🗑️ Reminder cancelled: **{self.reminder['message']}**",
                    view=None
                )

            @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: ui.Button):
                if interaction.user != self.user:
                    return await interaction.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                await interaction.response.edit_message(
                    content="❎ Cancel action aborted.",
                    view=None
                )

        if isinstance(src, discord.Interaction):
            await src.response.send_message("📋 Select a reminder to cancel:", view=CancelView(self))
        else:
            await src.send("📋 Select a reminder to cancel:", view=CancelView(self))


# ======================
# Setup
# ======================
async def setup(bot):
    await bot.add_cog(ReminderCog(bot))