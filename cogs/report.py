import discord
from discord.ext import commands
from discord.ui import View, Button
import json, os, asyncio, datetime

REPORTS_FILE = "/data/reports.json"
SETTINGS_FILE = "report_settings.json"

os.makedirs(os.path.dirname(REPORTS_FILE), exist_ok=True) if "/" in REPORTS_FILE else None
os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True) if "/" in SETTINGS_FILE else None

save_lock = asyncio.Lock()

# -------------------- JSON Helpers --------------------
def load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# -------------------- Duration Parsing --------------------
def parse_duration(duration: str):
    units = {
        "s": "seconds", "sec": "seconds", "second": "seconds", "seconds": "seconds",
        "m": "minutes", "min": "minutes", "minute": "minutes", "minutes": "minutes",
        "h": "hours", "hr": "hours", "hour": "hours", "hours": "hours",
        "d": "days", "day": "days", "days": "days",
        "w": "weeks", "week": "weeks", "weeks": "weeks"
    }
    num = "".join([c for c in duration if c.isdigit()])
    unit = "".join([c for c in duration if c.isalpha()]).lower()

    if not num or unit not in units:
        return None

    kwargs = {units[unit]: int(num)}
    return datetime.timedelta(**kwargs)

# -------------------- Report Buttons --------------------
class BaseReportButton(Button):
    def __init__(self, bot, report_id, label, style, emoji):
        super().__init__(label=label, style=style, emoji=emoji, custom_id=f"{label}-{report_id}")
        self.bot = bot
        self.report_id = str(report_id)

    def get_report(self):
        data = load_json(REPORTS_FILE)
        return data, data.get(self.report_id)

    def update_report(self, data):
        save_json(REPORTS_FILE, data)

    async def send_ephemeral(self, interaction, msg):
        await interaction.response.send_message(msg, ephemeral=True)

class ReportView(View):
    def __init__(self, bot, report_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.report_id = str(report_id)
        self.add_item(ReportSolveButton(bot, self.report_id))
        self.add_item(ReportAskDMButton(bot, self.report_id))
        self.add_item(ReportDismissButton(bot, self.report_id))
        self.add_item(ReportDeleteButton(bot, self.report_id))
        self.add_item(ReportKickButton(bot, self.report_id))
        self.add_item(ReportBanButton(bot, self.report_id))
        self.add_item(ReportMuteButton(bot, self.report_id))

# -------- Buttons --------
class ReportSolveButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "Solve", discord.ButtonStyle.success, "✅", row=0)

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await self.send_ephemeral(interaction, "❌ You don’t have permission.")
        data, report = self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")

        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            embed = discord.Embed(
                title="✅ Report Solved",
                description=f"Your report in **{interaction.guild.name}** has been solved by {interaction.user.mention}.",
                color=discord.Color.green()
            )
            embed.add_field(name="Report ID", value=self.report_id)
            try: await reporter.send(embed=embed)
            except: pass

        report["status"] = "solved"
        report["solver_id"] = interaction.user.id
        self.update_report(data)
        await self.send_ephemeral(interaction, "✅ Report marked as solved.")

class ReportAskDMButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "Ask DM", discord.ButtonStyle.primary, "💬", row=0)

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await self.send_ephemeral(interaction, "❌ You don’t have permission.")
        data, report = self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")
        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            embed = discord.Embed(
                title="💬 Staff Requested DM",
                description=f"A staff member in **{interaction.guild.name}** ({interaction.user.mention}) asked you to DM them.",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Report ID", value=self.report_id)
            try: await reporter.send(embed=embed)
            except: pass
        await self.send_ephemeral(interaction, "📤 Requested DM.")

class ReportDismissButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "Dismiss", discord.ButtonStyle.secondary, "❌", row=0)

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await self.send_ephemeral(interaction, "❌ You don’t have permission.")
        data, report = self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")
        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            embed = discord.Embed(
                title="❌ Report Dismissed",
                description=f"Your report in **{interaction.guild.name}** was dismissed by {interaction.user.mention}.",
                color=discord.Color.red()
            )
            embed.add_field(name="Report ID", value=self.report_id)
            try: await reporter.send(embed=embed)
            except: pass
        report["status"] = "dismissed"
        report["dismissed_by"] = interaction.user.id
        self.update_report(data)
        await self.send_ephemeral(interaction, "✅ Report dismissed.")

class ReportDeleteButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "Delete", discord.ButtonStyle.danger, "🗑️", row=0)

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await self.send_ephemeral(interaction, "❌ You don’t have permission.")
        data, report = self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")
        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            embed = discord.Embed(
                title="🗑️ Report Deleted",
                description=f"Your report in **{interaction.guild.name}** was deleted by {interaction.user.mention}.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Report ID", value=self.report_id)
            try: await reporter.send(embed=embed)
            except: pass
        data.pop(self.report_id, None)
        save_json(REPORTS_FILE, data)
        await self.send_ephemeral(interaction, "✅ Report deleted.")

class ReportKickButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "Kick", discord.ButtonStyle.danger, "⚒️", row=1)

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.kick_members:
            return await self.send_ephemeral(interaction, "❌ No permission to kick.")
        data, report = self.get_report()
        member = interaction.guild.get_member(report["reported_id"])
        if member:
            try:
                embed = discord.Embed(
                    title="⚒️ Punished: Kick",
                    description=f"You were reported in **{interaction.guild.name}** and punished with **Kick**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Punished by", value=interaction.user.mention)
                await member.send(embed=embed)
            except: pass
            await member.kick(reason=f"Report {self.report_id}")
        report["status"] = "punished"
        report["punishment"] = "Kick"
        report["punished_by"] = interaction.user.id
        self.update_report(data)
        await self.send_ephemeral(interaction, "✅ User kicked.")

class ReportBanButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "Ban", discord.ButtonStyle.danger, "🔨", row=1)

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.ban_members:
            return await self.send_ephemeral(interaction, "❌ No permission to ban.")
        data, report = self.get_report()
        member = interaction.guild.get_member(report["reported_id"])
        if member:
            try:
                embed = discord.Embed(
                    title="⚒️ Punished: Ban",
                    description=f"You were reported in **{interaction.guild.name}** and punished with **Ban**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Punished by", value=interaction.user.mention)
                await member.send(embed=embed)
            except: pass
            await member.ban(reason=f"Report {self.report_id}")
        report["status"] = "punished"
        report["punishment"] = "Ban"
        report["punished_by"] = interaction.user.id
        self.update_report(data)
        await self.send_ephemeral(interaction, "✅ User banned.")

class ReportMuteButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "Mute", discord.ButtonStyle.secondary, "🔇"* row=1)

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.moderate_members:
            return await self.send_ephemeral(interaction, "❌ No permission to mute.")
        data, report = self.get_report()
        member = interaction.guild.get_member(report["reported_id"])
        settings = load_json(SETTINGS_FILE)
        guild_settings = settings.get(str(interaction.guild.id), {})
        duration = guild_settings.get("mute_duration", "10m")
        td = parse_duration(duration) or datetime.timedelta(minutes=10)
        if member:
            try:
                embed = discord.Embed(
                    title="⚒️ Punished: Timeout",
                    description=f"You were reported in **{interaction.guild.name}** and punished with a timeout for **{duration}**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Punished by", value=interaction.user.mention)
                await member.send(embed=embed)
            except: pass
            await member.timeout_for(td, reason=f"Report {self.report_id}")
        report["status"] = "punished"
        report["punishment"] = f"Timeout {duration}"
        report["punished_by"] = interaction.user.id
        self.update_report(data)
        await self.send_ephemeral(interaction, f"✅ User muted for {duration}.")

# -------------------- Cog --------------------
class Reports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reports = load_json(REPORTS_FILE)
        self.settings = load_json(SETTINGS_FILE)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def setreport(self, ctx, channel: discord.TextChannel):
        """Set report channel"""
        self.settings[str(ctx.guild.id)] = self.settings.get(str(ctx.guild.id), {})
        self.settings[str(ctx.guild.id)]["report_channel"] = channel.id
        save_json(SETTINGS_FILE, self.settings)
        await ctx.send(f"✅ Report channel set to {channel.mention}")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def setmute(self, ctx, duration: str):
        """Set default mute duration (e.g. 10m, 2h, 1d)"""
        td = parse_duration(duration)
        if not td:
            return await ctx.send("❌ Invalid format! Use `10m`, `2h`, `1d`, etc.")
        self.settings[str(ctx.guild.id)] = self.settings.get(str(ctx.guild.id), {})
        self.settings[str(ctx.guild.id)]["mute_duration"] = duration
        save_json(SETTINGS_FILE, self.settings)
        await ctx.send(f"✅ Mute duration set to **{duration}**.")

    @commands.command()
    async def report(self, ctx, member: discord.Member, *, reason: str):
        """Report a member"""
        guild_settings = self.settings.get(str(ctx.guild.id), {})
        if "report_channel" not in guild_settings:
            return await ctx.send("❌ Report channel not set.")
        report_id = str(len(self.reports) + 1)
        report = {
            "id": report_id,
            "reporter_id": ctx.author.id,
            "reported_id": member.id,
            "reason": reason,
            "status": "pending",
            "time": str(datetime.datetime.utcnow())
        }
        self.reports[report_id] = report
        save_json(REPORTS_FILE, self.reports)
        channel = ctx.guild.get_channel(guild_settings["report_channel"])
        embed = discord.Embed(title="🚨 New Report", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Report ID", value=report_id)
        embed.add_field(name="Reporter", value=ctx.author.mention)
        embed.add_field(name="Reported User", value=member.mention)
        embed.add_field(name="Reason", value=reason, inline=False)
        await channel.send(embed=embed, view=ReportView(self.bot, report_id))
        await ctx.send("✅ Your report has been submitted!")

    @commands.command()
    async def myreports(self, ctx):
        """Show your reports"""
        my_reps = [r for r in self.reports.values() if r["reporter_id"] == ctx.author.id]
        if not my_reps:
            return await ctx.send("❌ You have no reports.")
        embed = discord.Embed(title="📋 My Reports", color=discord.Color.blue())
        for r in my_reps:
            embed.add_field(name=f"ID {r['id']} ({r['status']})", value=f"<@{r['reported_id']}> - {r['reason']}", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def reportinfo(self, ctx, report_id: str):
        """Detailed info about a report"""
        report = self.reports.get(report_id)
        if not report:
            return await ctx.send("❌ Report not found.")
        embed = discord.Embed(title=f"ℹ️ Report Info {report_id}", color=discord.Color.green())
        embed.add_field(name="Reporter", value=f"<@{report['reporter_id']}>")
        embed.add_field(name="Reported", value=f"<@{report['reported_id']}>")
        embed.add_field(name="Reason", value=report["reason"], inline=False)
        embed.add_field(name="Status", value=report["status"])
        if "punishment" in report:
            embed.add_field(name="Punishment", value=report["punishment"])
            embed.add_field(name="Staff", value=f"<@{report['punished_by']}>")
        elif "solver_id" in report:
            embed.add_field(name="Solved by", value=f"<@{report['solver_id']}>")
        elif "dismissed_by" in report:
            embed.add_field(name="Dismissed by", value=f"<@{report['dismissed_by']}>")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        # reattach persistent buttons
        for rid in self.reports.keys():
            self.bot.add_view(ReportView(self.bot, rid))
        print("✅ Reports cog loaded with persistent buttons.")

async def setup(bot):
    await bot.add_cog(Reports(bot))