import discord
from discord.ext import commands, tasks
from discord import ui, app_commands
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

    # background checker
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
    # Prefix Command - $remindme
    # ======================
    @commands.command(name="remindme")
    async def remindme_prefix(self, ctx, when: str = None, *, message: str = "No message"):
        await self._create_reminder(ctx, ctx.author, when, message)

    # ======================
    # Slash Command - /remindme
    # ======================
    @app_commands.command(name="remindme", description="Set a reminder")
    async def remindme_slash(self, interaction: discord.Interaction, when: str = None, message: str = "No message"):
        await self._create_reminder(interaction, interaction.user, when, message, is_slash=True)

    # Core reminder logic
    async def _create_reminder(self, ctx_or_inter, user, when: str, message: str, is_slash=False):
        seconds = parse_time(when)
        if seconds is None:
            text = "❌ Invalid time format. Example: `10m`, `1h30min`, `2week`, `1mon`"
            return await (ctx_or_inter.response.send_message(text, ephemeral=True) if is_slash else ctx_or_inter.send(text))

        end_time = int(datetime.utcnow().timestamp() + seconds)
        reminder = {"user": user.id, "message": message, "time": end_time}
        self.reminders.append(reminder)
        save_reminders(self.reminders)

        # instant reminder
        if seconds == 0:
            await user.send(f"⏰ Reminder: **{message}**")
            self.reminders.remove(reminder)
            save_reminders(self.reminders)
            text = f"✅ Sent your instant reminder: **{message}**"
            return await (ctx_or_inter.response.send_message(text, ephemeral=True) if is_slash else ctx_or_inter.send(text))

        self.bot.loop.create_task(self.reminder_task(reminder, seconds))

        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=f"**Message:** {message}\n**Time:** <t:{int(end_time)}:R>",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Requested by {user}", icon_url=user.avatar.url if user.avatar else None)

        if is_slash:
            await ctx_or_inter.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx_or_inter.send(embed=embed)

    # ======================
    # List Reminders
    # ======================
    @commands.command(name="reminders")
    async def reminders_prefix(self, ctx):
        await self._list_reminders(ctx, ctx.author)

    @app_commands.command(name="reminders", description="List your active reminders")
    async def reminders_slash(self, interaction: discord.Interaction):
        await self._list_reminders(interaction, interaction.user, is_slash=True)

    async def _list_reminders(self, ctx_or_inter, user, is_slash=False):
        user_reminders = [r for r in self.reminders if r["user"] == user.id]
        if not user_reminders:
            text = "📭 You have no active reminders."
            return await (ctx_or_inter.response.send_message(text, ephemeral=True) if is_slash else ctx_or_inter.send(text))

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
                    value=f"⏰ <t:{int(r['time'])}:R>",
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

        if is_slash:
            await ctx_or_inter.response.send_message(embed=make_embed(page), view=ReminderView(), ephemeral=True)
        else:
            await ctx_or_inter.send(embed=make_embed(page), view=ReminderView())

    # ======================
    # Cancel Reminder
    # ======================
    @commands.command(name="cancelreminder", aliases=["cr", "rcancel"])
    async def cancel_prefix(self, ctx):
        await self._cancel_reminder(ctx, ctx.author)

    @app_commands.command(name="cancelreminder", description="Cancel one of your reminders")
    async def cancel_slash(self, interaction: discord.Interaction):
        await self._cancel_reminder(interaction, interaction.user, is_slash=True)

    async def _cancel_reminder(self, ctx_or_inter, user, is_slash=False):
        user_reminders = [r for r in self.reminders if r["user"] == user.id]
        if not user_reminders:
            text = "📭 You have no active reminders to cancel."
            return await (ctx_or_inter.response.send_message(text, ephemeral=True) if is_slash else ctx_or_inter.send(text))

        options = [
            discord.SelectOption(
                label=r["message"][:50],
                description=f"Reminds <t:{int(r['time'])}:R>",
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
                    await inter.response.edit_message(content=f"🗑️ Reminder cancelled: **{reminder['message']}**", embed=None, view=None)

                @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(btnself, inter, button):
                    if inter.user != user:
                        return await inter.response.send_message("❌ This isn’t your menu!", ephemeral=True)
                    await inter.response.edit_message(content="❎ Cancel action aborted.", embed=None, view=None)

                await interaction.response.edit_message(
                    content=f"⚠️ Do you really want to cancel **{reminder['message']}**?",
                    view=confirm_view
                )

        if is_slash:
            await ctx_or_inter.response.send_message("📋 Select a reminder to cancel:", view=CancelView(), ephemeral=True)
        else:
            await ctx_or_inter.send("📋 Select a reminder to cancel:", view=CancelView())

# ======================
# Setup
# ======================
async def setup(bot):
    await bot.add_cog(ReminderCog(bot))