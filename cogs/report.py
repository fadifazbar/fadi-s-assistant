import discord
from discord.ext import commands
from discord.ui import View, Button
import json, os, asyncio
from datetime import datetime, timedelta

DATA_FILE = "/data/reports.json"
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True) if "/" in DATA_FILE else None
save_lock = asyncio.Lock()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"servers": {}, "reports": {}, "counter": 1}

async def save_data(data):
    async with save_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

class ReportView(View):
    def __init__(self, bot, report_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.report_id = str(report_id)

        # ✅ Solve button
        self.add_item(ReportSolveButton(bot, self.report_id))
        # 💬 Ask DM
        self.add_item(ReportAskDMButton(bot, self.report_id))
        # ❌ Dismiss
        self.add_item(ReportDismissButton(bot, self.report_id))
        # 🗑 Delete
        self.add_item(ReportDeleteButton(bot, self.report_id))
        # ⚒ Kick/Ban/Mute
        self.add_item(ReportKickButton(bot, self.report_id))
        self.add_item(ReportBanButton(bot, self.report_id))
        self.add_item(ReportMuteButton(bot, self.report_id))

class BaseReportButton(Button):
    def __init__(self, bot, report_id, label, style, emoji):
        super().__init__(label=label, style=style, emoji=emoji, custom_id=f"{label}-{report_id}")
        self.bot = bot
        self.report_id = str(report_id)

    async def get_report(self):
        data = load_data()
        return data, data["reports"].get(self.report_id)

    async def update_report(self, data):
        await save_data(data)

    async def send_ephemeral(self, interaction, msg):
        await interaction.response.send_message(msg, ephemeral=True)

class ReportSolveButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "solve", discord.ButtonStyle.success, "✅")

    async def callback(self, interaction: discord.Interaction):
        data, report = await self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")

        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            try:
                embed = discord.Embed(
                    title="✅ Your report has been solved!",
                    description=f"The report you sent in **{interaction.guild.name}** has been solved by {interaction.user.mention}!",
                    color=discord.Color.green()
                )
                embed.add_field(name="🆔 Report ID", value=self.report_id)
                await reporter.send(embed=embed)
                await self.send_ephemeral(interaction, "✅ Solved the report and notified the member!")
            except:
                await self.send_ephemeral(interaction, "❌ Failed to send the DM.")
        report["status"] = "solved"
        report["solver_id"] = interaction.user.id
        await self.update_report(data)

class ReportAskDMButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "askdm", discord.ButtonStyle.primary, "💬")

    async def callback(self, interaction: discord.Interaction):
        data, report = await self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")
        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            try:
                embed = discord.Embed(
                    title="💬 You have been requested for a DM",
                    description=f"A staff member from **{interaction.guild.name}** has asked you to send them a DM.",
                    color=discord.Color.blurple()
                )
                embed.add_field(name="⚒️ The Staff Member", value=interaction.user.mention)
                embed.add_field(name="🆔 Report ID", value=self.report_id)
                await reporter.send(embed=embed)
                await self.send_ephemeral(interaction, "📤 Sent a DM successfully!")
            except:
                await self.send_ephemeral(interaction, "❌ Failed to send the DM.")

class ReportDismissButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "dismiss", discord.ButtonStyle.secondary, "❌")

    async def callback(self, interaction: discord.Interaction):
        data, report = await self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")
        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            try:
                embed = discord.Embed(
                    title="❌ Your report has been dismissed",
                    description=f"The report you submitted in **{interaction.guild.name}** was dismissed by {interaction.user.mention}.",
                    color=discord.Color.red()
                )
                embed.add_field(name="🆔 Report ID", value=self.report_id)
                await reporter.send(embed=embed)
                await self.send_ephemeral(interaction, "✅ Report dismissed and user notified!")
            except:
                await self.send_ephemeral(interaction, "❌ Failed to notify user.")
        report["status"] = "dismissed"
        report["dismissed_by"] = interaction.user.id
        await self.update_report(data)

class ReportDeleteButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "delete", discord.ButtonStyle.danger, "🗑️")

    async def callback(self, interaction: discord.Interaction):
        data, report = await self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")
        reporter = interaction.guild.get_member(report["reporter_id"])
        if reporter:
            try:
                embed = discord.Embed(
                    title="🗑️ Your report has been deleted",
                    description=f"The report you submitted in **{interaction.guild.name}** has been deleted by {interaction.user.mention}.",
                    color=discord.Color.orange()
                )
                embed.add_field(name="🆔 Report ID", value=self.report_id)
                await reporter.send(embed=embed)
            except:
                pass
        del data["reports"][self.report_id]
        await self.update_report(data)
        await self.send_ephemeral(interaction, "✅ Report deleted!")

class ReportKickButton(BaseReportButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id, "kick", discord.ButtonStyle.danger, "⚒️")

    async def callback(self, interaction: discord.Interaction):
        data, report = await self.get_report()
        if not report: return await self.send_ephemeral(interaction, "❌ Report not found.")
        member = interaction.guild.get_member(report["reported_id"])
        if member:
            try:
                embed = discord.Embed(
                    title="⚒️ You have been punished",
                    description=f"You have been reported in **{interaction.guild.name}** and the report has resulted in a punishment: **Kick**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Punished by", value=interaction.user.mention)
                embed.add_field(name="🆔 Report ID", value=self.report_id)
                await member.send(embed=embed)
            except: pass
            await member.kick(reason=f"Report {self.report_id}")
            await self.send_ephemeral(interaction, "✅ User kicked!")
        report["status"] = "punished"
        report["punishment"] = "Kick"
        report["punished_by"] = interaction.user.id
        await self.update_report(data)

class ReportBanButton(ReportKickButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id)
        self.label = "ban"
        self.emoji = "🔨"

    async def callback(self, interaction: discord.Interaction):
        data, report = await self.get_report()
        member = interaction.guild.get_member(report["reported_id"])
        if member:
            try:
                embed = discord.Embed(
                    title="⚒️ You have been punished",
                    description=f"You have been reported in **{interaction.guild.name}** and the report has resulted in a punishment: **Ban**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Punished by", value=interaction.user.mention)
                embed.add_field(name="🆔 Report ID", value=self.report_id)
                await member.send(embed=embed)
            except: pass
            await member.ban(reason=f"Report {self.report_id}")
            await self.send_ephemeral(interaction, "✅ User banned!")
        report["status"] = "punished"
        report["punishment"] = "Ban"
        report["punished_by"] = interaction.user.id
        await self.update_report(data)

class ReportMuteButton(ReportKickButton):
    def __init__(self, bot, report_id):
        super().__init__(bot, report_id)
        self.label = "mute"
        self.emoji = "🔇"

    async def callback(self, interaction: discord.Interaction):
        data, report = await self.get_report()
        member = interaction.guild.get_member(report["reported_id"])
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if member and mute_role:
            try:
                embed = discord.Embed(
                    title="⚒️ You have been punished",
                    description=f"You have been reported in **{interaction.guild.name}** and the report has resulted in a punishment: **10m Mute**.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Punished by", value=interaction.user.mention)
                embed.add_field(name="🆔 Report ID", value=self.report_id)
                await member.send(embed=embed)
            except: pass
            await member.add_roles(mute_role)
            await self.send_ephemeral(interaction, "✅ User muted for 10 minutes!")
            await asyncio.sleep(600)
            await member.remove_roles(mute_role)
        report["status"] = "punished"
        report["punishment"] = "Mute"
        report["punished_by"] = interaction.user.id
        await self.update_report(data)

class Reports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def setreport(self, ctx, channel: discord.TextChannel):
        data = load_data()
        data["servers"][str(ctx.guild.id)] = {"report_channel": channel.id}
        await save_data(data)
        await ctx.send(f"✅ Report channel set to {channel.mention}")

    @commands.command()
    async def report(self, ctx, member: discord.Member, *, reason: str):
        data = load_data()
        guild_data = data["servers"].get(str(ctx.guild.id))
        if not guild_data or "report_channel" not in guild_data:
            return await ctx.send("❌ Report channel not set.")
        report_id = data["counter"]
        data["counter"] += 1
        report = {
            "id": report_id,
            "reporter_id": ctx.author.id,
            "reported_id": member.id,
            "reason": reason,
            "status": "pending",
            "time": str(datetime.utcnow())
        }
        data["reports"][str(report_id)] = report
        await save_data(data)

        channel = ctx.guild.get_channel(guild_data["report_channel"])
        embed = discord.Embed(title="🚨 New Report", color=discord.Color.orange())
        embed.add_field(name="🆔 Report ID", value=str(report_id))
        embed.add_field(name="👤 Reporter", value=ctx.author.mention, inline=False)
        embed.add_field(name="🎯 Reported User", value=member.mention, inline=False)
        embed.add_field(name="📌 Reason", value=reason, inline=False)
        embed.timestamp = datetime.utcnow()

        await channel.send(embed=embed, view=ReportView(self.bot, report_id))
        await ctx.send("✅ Your report has been submitted!")

    @commands.command()
    async def myreports(self, ctx):
        data = load_data()
        reports = [r for r in data["reports"].values() if r["reporter_id"] == ctx.author.id]
        if not reports:
            return await ctx.send("❌ You have no reports.")
        embed = discord.Embed(title="📋 My Reports", color=discord.Color.blue())
        for r in reports:
            embed.add_field(
                name=f"🆔 {r['id']} - {r['status']}",
                value=f"🎯 <@{r['reported_id']}> | 📌 {r['reason']}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command()
    async def reportinfo(self, ctx, report_id: int):
        data = load_data()
        report = data["reports"].get(str(report_id))
        if not report:
            return await ctx.send("❌ Report not found.")
        embed = discord.Embed(title=f"ℹ️ Report Info: {report_id}", color=discord.Color.green())
        embed.add_field(name="👤 Reporter", value=f"<@{report['reporter_id']}>")
        embed.add_field(name="🎯 Reported", value=f"<@{report['reported_id']}>")
        embed.add_field(name="📌 Reason", value=report["reason"], inline=False)
        embed.add_field(name="📂 Status", value=report["status"], inline=False)
        if "punishment" in report:
            embed.add_field(name="⚒️ Punishment", value=report["punishment"])
            embed.add_field(name="Staff", value=f"<@{report['punished_by']}>")
        elif "solver_id" in report:
            embed.add_field(name="Solved by", value=f"<@{report['solver_id']}>")
        elif "dismissed_by" in report:
            embed.add_field(name="Dismissed by", value=f"<@{report['dismissed_by']}>")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Reports(bot))