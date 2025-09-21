# cogs/reminder_cog.py
import os
import re
import json
import uuid
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands, ui

# Path used on Railway: adjust if needed
DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "reminders.json")

# Optional: set GUILD_ID env var for fast slash command registration during testing
GUILD_ID = os.environ.get("GUILD_ID")  # e.g. "123456789012345678"

# Ensure storage file
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

def load_reminders() -> List[Dict]:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders: List[Dict]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def parse_time(timestr: Optional[str]) -> Optional[int]:
    """
    Accepts flexible formats like:
      1h30m
      2d4h10m5s
      45s
    Returns total seconds (int). If timestr is None or empty -> 0 (instant).
    If invalid -> None.
    """
    if not timestr:
        return 0
    s = timestr.strip().lower().replace(" ", "")
    # find tokens like 10d, 4h, 30m, 5s in any order
    tokens = re.findall(r'(\d+[dhms])', s)
    if not tokens:
        return None
    total = 0
    for t in tokens:
        num = int(re.match(r'(\d+)', t).group(1))
        unit = t[-1]
        if unit == 'd':
            total += num * 86400
        elif unit == 'h':
            total += num * 3600
        elif unit == 'm':
            total += num * 60
        elif unit == 's':
            total += num
    return total

def format_timedelta(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    parts = []
    days, seconds = divmod(seconds, 86400)
    hrs, seconds = divmod(seconds, 3600)
    mins, secs = divmod(seconds, 60)
    if days: parts.append(f"{days}d")
    if hrs: parts.append(f"{hrs}h")
    if mins: parts.append(f"{mins}m")
    if secs or not parts: parts.append(f"{secs}s")
    return " ".join(parts)

class ReminderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminders = load_reminders()  # list of dicts
        # runtime tasks mapping: reminder_id -> asyncio.Task
        self._tasks: Dict[str, asyncio.Task] = {}
        # resume scheduling after bot ready
        self.bot.loop.create_task(self._resume_reminders())

    # Called when cog is loaded: sync app commands (fast if GUILD_ID is set)
    async def cog_load(self) -> None:
        try:
            if GUILD_ID:
                await self.bot.tree.sync(guild=discord.Object(id=int(GUILD_ID)))
                print(f"[ReminderCog] Synced app commands to guild {GUILD_ID}")
            else:
                await self.bot.tree.sync()
                print("[ReminderCog] Synced global app commands")
        except Exception as e:
            print("[ReminderCog] Failed to sync app commands:", e)

    async def _resume_reminders(self):
        await self.bot.wait_until_ready()
        now = datetime.utcnow().timestamp()
        # schedule not-yet-expired reminders, fire expired ones immediately
        for rem in self.reminders.copy():
            remaining = rem["time"] - now
            if remaining > 0:
                task = self.bot.loop.create_task(self._reminder_task(rem["id"], remaining))
                self._tasks[rem["id"]] = task
            else:
                # expired while offline -> fire delayed message
                delay = int(now - rem["time"])
                try:
                    user = await self.bot.fetch_user(rem["user"])
                    if user:
                        await user.send(f"⏰ Reminder (delayed {format_timedelta(delay)}): {rem['message']}")
                except Exception as e:
                    print(f"[ReminderCog] failed to DM delayed reminder: {e}")
                # remove expired
                try:
                    self.reminders.remove(rem)
                except ValueError:
                    pass
        save_reminders(self.reminders)

    async def _reminder_task(self, reminder_id: str, wait_seconds: int):
        await asyncio.sleep(wait_seconds)
        # find reminder by id; maybe it was canceled
        rem = next((r for r in self.reminders if r["id"] == reminder_id), None)
        if not rem:
            self._tasks.pop(reminder_id, None)
            return
        try:
            user = await self.bot.fetch_user(rem["user"])
            if user:
                await user.send(f"⏰ Reminder: {rem['message']}")
        except Exception as e:
            print(f"[ReminderCog] error sending reminder DM: {e}")
        # remove and save
        try:
            self.reminders.remove(rem)
            save_reminders(self.reminders)
        except ValueError:
            pass
        self._tasks.pop(reminder_id, None)

    # ---------- PREFIX COMMAND ----------
    @commands.command(name="remindme")
    async def remindme_prefix(self, ctx: commands.Context, *args):
        """
        Usage:
          $remindme 5m Study time
          $remindme Study time   (instant)
        """
        if len(args) == 0:
            return await ctx.send("Usage: `$remindme [time] message`. Examples: `$remindme 5m Study` or `$remindme Study now`")

        # If first token looks like a time, treat it as time; else time omitted
        maybe_time = args[0]
        seconds = parse_time(maybe_time)
        if seconds is None:
            # no time provided -> whole args is message (instant)
            seconds = 0
            message = " ".join(args)
            when_text = None
        else:
            message = " ".join(args[1:]).strip()
            when_text = maybe_time
            if not message:
                return await ctx.send("Please include a message for the reminder. Example: `$remindme 5m Study`")

        reminder_id = str(uuid.uuid4())
        end_time = datetime.utcnow().timestamp() + seconds
        rem = {"id": reminder_id, "user": ctx.author.id, "message": message, "time": end_time, "created_at": datetime.utcnow().timestamp()}
        self.reminders.append(rem)
        save_reminders(self.reminders)

        if seconds == 0:
            # instant: send DM, remove from store
            try:
                await ctx.author.send(f"⏰ Reminder: {message}")
            except Exception:
                pass
            try:
                self.reminders.remove(rem)
                save_reminders(self.reminders)
            except ValueError:
                pass
            return await ctx.send(f"✅ Sent your instant reminder: **{message}**")

        # scheduled
        task = self.bot.loop.create_task(self._reminder_task(reminder_id, seconds))
        self._tasks[reminder_id] = task
        return await ctx.send(f"✅ I will remind you in {format_timedelta(seconds)}: **{message}**")

    # ---------- SLASH COMMAND ----------
    @app_commands.command(name="remindme", description="Set a reminder. Time is optional (e.g. 1h30m, 5m, 45s).")
    async def remindme_slash(self, interaction: discord.Interaction, when: Optional[str] = None, message: Optional[str] = None):
        """
        Slash usage in UI:
          /remindme when:5m message:Study
        If the user supplies only one argument because of input order, we accept it:
          /remindme when:Study  -> becomes instant reminder
        (We attempt to be flexible.)
        """
        # If user used only one field, handle ambiguity
        if not message and when:
            # assume they meant message only (instant)
            # detect if 'when' is actually a time token; if yes but no message, complain
            maybe_seconds = parse_time(when)
            if maybe_seconds is None:
                # treat 'when' as message text
                message = when
                when = None
            else:
                return await interaction.response.send_message("Please include a message for the reminder. Example: `/remindme when:5m message:Study`", ephemeral=True)

        if not message:
            return await interaction.response.send_message("Usage: `/remindme when:5m message:Study` or `/remindme message:Study` (time optional).", ephemeral=True)

        seconds = parse_time(when)
        if seconds is None:
            return await interaction.response.send_message("❌ Invalid time format. Example: `10m`, `1h30m`, `2d4h` or combination like `1h30m`", ephemeral=True)

        reminder_id = str(uuid.uuid4())
        end_time = datetime.utcnow().timestamp() + seconds
        rem = {"id": reminder_id, "user": interaction.user.id, "message": message, "time": end_time, "created_at": datetime.utcnow().timestamp()}
        self.reminders.append(rem)
        save_reminders(self.reminders)

        if seconds == 0:
            try:
                await interaction.user.send(f"⏰ Reminder: {message}")
            except Exception:
                pass
            try:
                self.reminders.remove(rem)
                save_reminders(self.reminders)
            except ValueError:
                pass
            return await interaction.response.send_message(f"✅ Sent your instant reminder: **{message}**", ephemeral=True)

        task = self.bot.loop.create_task(self._reminder_task(reminder_id, seconds))
        self._tasks[reminder_id] = task
        return await interaction.response.send_message(f"✅ I will remind you in {format_timedelta(seconds)}: **{message}**", ephemeral=True)

    # ---------- LIST REMINDERS (prefix) ----------
    @commands.command(name="listreminders")
    async def listreminders(self, ctx: commands.Context):
        await self._list_reminders_ui(ctx.author, send_fn=lambda **k: ctx.send(**k))

    # ---------- LIST REMINDERS (slash) ----------
    @app_commands.command(name="listreminders", description="List your active reminders (paginated).")
    async def listreminders_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        content = {}
        async def send_fn(**k):
            await interaction.followup.send(**k)
        await self._list_reminders_ui(interaction.user, send_fn=send_fn)

    async def _list_reminders_ui(self, user: discord.User, send_fn):
        user_reminders = [r for r in self.reminders if r["user"] == user.id]
        if not user_reminders:
            return await send_fn(content="📭 You have no active reminders!")

        # sort by time ascending
        user_reminders.sort(key=lambda r: r["time"])
        per_page = 5

        class PagerView(ui.View):
            def __init__(self, cog, author, reminders, per_page):
                super().__init__(timeout=120)
                self.cog = cog
                self.author = author
                self.reminders = reminders
                self.per_page = per_page
                self.page = 0

            def _make_embed(self):
                total_pages = (len(self.reminders) - 1) // self.per_page + 1
                start = self.page * self.per_page
                end = start + self.per_page
                e = discord.Embed(title=f"📝 Your Reminders (Page {self.page+1}/{total_pages})", color=discord.Color.blurple())
                now = datetime.utcnow().timestamp()
                for idx, r in enumerate(self.reminders[start:end], start=start+1):
                    left = int(r["time"] - now)
                    if left < 0:
                        left_text = "Expired"
                    else:
                        left_text = format_timedelta(left)
                    # truncate message if long
                    msg = r["message"]
                    if len(msg) > 80:
                        msg = msg[:77] + "..."
                    e.add_field(name=f"{idx}. {msg}", value=f"Time left: {left_text}", inline=False)
                return e

            @ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
            async def prev(self, interaction: discord.Interaction, button: ui.Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("This is not your pager.", ephemeral=True)
                if self.page > 0:
                    self.page -= 1
                    await interaction.response.edit_message(embed=self._make_embed(), view=self)
                else:
                    await interaction.response.defer()

            @ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
            async def next(self, interaction: discord.Interaction, button: ui.Button):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("This is not your pager.", ephemeral=True)
                if (self.page + 1) * self.per_page < len(self.reminders):
                    self.page += 1
                    await interaction.response.edit_message(embed=self._make_embed(), view=self)
                else:
                    await interaction.response.defer()

        view = PagerView(self, user, user_reminders, per_page)
        embed = view._make_embed()
        await send_fn(embed=embed, view=view)

    # ---------- CANCEL REMINDER (prefix) ----------
    @commands.command(name="cancelreminder")
    async def cancelreminder(self, ctx: commands.Context):
        await self._cancel_reminder_ui(ctx.author, send_fn=lambda **k: ctx.send(**k))

    # ---------- CANCEL REMINDER (slash) ----------
    @app_commands.command(name="cancelreminder", description="Cancel one of your active reminders via select menu.")
    async def cancelreminder_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async def send_fn(**k):
            await interaction.followup.send(**k)
        await self._cancel_reminder_ui(interaction.user, send_fn=send_fn)

    async def _cancel_reminder_ui(self, user: discord.User, send_fn):
        user_reminders = [r for r in self.reminders if r["user"] == user.id]
        if not user_reminders:
            return await send_fn(content="📭 You have no active reminders!")

        # build select options with unique values = reminder id
        options = []
        now = datetime.utcnow().timestamp()
        for r in user_reminders:
            left = int(r["time"] - now)
            left_text = format_timedelta(max(0, left))
            label = r["message"]
            if len(label) > 90:
                label = label[:87] + "..."
            desc = f"In {left_text}"
            options.append(discord.SelectOption(label=label, description=desc, value=r["id"]))

        class CancelSelect(ui.View):
            def __init__(self, cog, author, reminders, options):
                super().__init__(timeout=60)
                self.cog = cog
                self.author = author
                self.reminders = reminders
                self.add_item(ui.Select(placeholder="Select a reminder to cancel ❌", options=options, max_values=1))

            @ui.select()
            async def select_callback(self, interaction: discord.Interaction, select: ui.Select):
                if interaction.user.id != self.author.id:
                    return await interaction.response.send_message("This select is not for you.", ephemeral=True)
                rid = select.values[0]
                rem = next((x for x in self.reminders if x["id"] == rid), None)
                if not rem:
                    return await interaction.response.edit_message(content="That reminder no longer exists.", embed=None, view=None)
                # cancel scheduled task (if exists)
                task = self.cog._tasks.pop(rid, None)
                if task and not task.done():
                    task.cancel()
                try:
                    self.cog.reminders.remove(rem)
                    save_reminders(self.cog.reminders)
                except ValueError:
                    pass
                await interaction.response.edit_message(content=f"✅ Reminder **{rem['message']}** cancelled!", embed=None, view=None)

        view = CancelSelect(self, user, user_reminders, options)
        embed = discord.Embed(title="❌ Cancel a Reminder", description="Choose one of your reminders below:", color=discord.Color.red())
        await send_fn(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(ReminderCog(bot))