import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os, asyncio
from datetime import datetime, timedelta

DATA_FILE = "warns.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"warnings": {}, "punishments": {}, "timeouts": {}}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

class Warnings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_timeouts.start()

    def cog_unload(self):
        self.check_timeouts.cancel()

    # ---------------- Utilities ----------------
    def parse_time(self, time_str: str) -> int:
        units = {"s":1, "m":60, "h":3600, "d":86400, "w":604800, "mon":2592000}
        for u, mult in units.items():
            if time_str.lower().endswith(u):
                return int(time_str[:-len(u)]) * mult
        return int(time_str)  # fallback

    def punishment_normalize(self, action: str):
        a = action.strip().lower()
        if a in ("mute", "timeout"): return "Mute"
        if a == "kick": return "Kick"
        if a == "ban": return "Ban"
        return None

    async def dm_warned_user(self, member: discord.Member, guild: discord.Guild, warn_no: int, reason: str, action_taken: str | None):
        try:
            emb = discord.Embed(title="⚠️ You were warned", color=discord.Color.orange(), timestamp=datetime.utcnow())
            emb.add_field(name="Server", value=f"{guild.name} (`{guild.id}`)", inline=False)
            emb.add_field(name="Warning #", value=str(warn_no), inline=True)
            emb.add_field(name="Reason", value=reason, inline=False)
            emb.add_field(name="What happened", value=action_taken or "No immediate punishment", inline=False)
            emb.set_footer(text="Please follow the server rules.")
            await member.send(embed=emb)
        except Exception:
            pass  # user has DMs off or blocked the bot

    # ---------------- Warn Command ----------------
    @commands.hybrid_command(name="warn", description="Warn a member")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        data["warnings"].setdefault(guild_id, {}).setdefault(user_id, [])

        warn_number = len(data["warnings"][guild_id][user_id]) + 1
        warn_entry = {
            "id": warn_number,
            "reason": reason,
            "moderator_id": str(ctx.author.id),
            "moderator_name": ctx.author.display_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        data["warnings"][guild_id][user_id].append(warn_entry)
        save_data(data)

        # Build response embed
        emb = discord.Embed(title="⚠️ User Warned", color=discord.Color.yellow(), timestamp=datetime.utcnow())
        emb.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        emb.add_field(name="Warning #", value=str(warn_number), inline=True)
        emb.add_field(name="Reason", value=reason, inline=False)
        emb.add_field(name="Warned by", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)

        # Check punishments
        action_taken_text = None
        punishments = data["punishments"].get(guild_id, {})
        p = punishments.get(str(warn_number))
        if p:
            action = p.get("action")
            duration = p.get("duration")
            if action == "Mute":
                if duration:
                    try:
                        seconds = self.parse_time(duration)
                        until = discord.utils.utcnow() + timedelta(seconds=seconds)
                        await member.edit(timed_out_until=until, reason=f"Warn #{warn_number} punishment")
                        data["timeouts"][str(member.id)] = {
                            "guild": guild_id,
                            "until": until.isoformat()
                        }
                        save_data(data)
                        action_taken_text = f"Muted for {duration}"
                        emb.add_field(name="Punishment", value=action_taken_text, inline=False)
                    except Exception as e:
                        emb.add_field(name="Punishment Error", value=f"Failed to mute: `{e}`", inline=False)
            elif action == "Kick":
                try:
                    await member.kick(reason=f"Warn #{warn_number} punishment")
                    action_taken_text = "Kicked"
                    emb.add_field(name="Punishment", value=action_taken_text, inline=False)
                except Exception as e:
                    emb.add_field(name="Punishment Error", value=f"Failed to kick: `{e}`", inline=False)
            elif action == "Ban":
                try:
                    await member.ban(reason=f"Warn #{warn_number} punishment")
                    action_taken_text = "Banned"
                    emb.add_field(name="Punishment", value=action_taken_text, inline=False)
                except Exception as e:
                    emb.add_field(name="Punishment Error", value=f"Failed to ban: `{e}`", inline=False)

        await ctx.send(embed=emb)
        await self.dm_warned_user(member, ctx.guild, warn_number, reason, action_taken_text)

    # ---------------- Warnings Command Group ----------------
    @commands.hybrid_group(name="warnings", description="Manage warnings")
    async def warnings(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=discord.Embed(
                description="Use `warnings list <member>` or `warnings clear <member> <warn_id>`",
                color=discord.Color.blurple())
            )

    @warnings.command(name="list", description="List warnings for a member")
    async def list_warnings(self, ctx, member: discord.Member):
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        warns = data["warnings"].get(guild_id, {}).get(user_id, [])
        if not warns:
            return await ctx.send(embed=discord.Embed(
                description=f"✅ {member.mention} has no warnings.",
                color=discord.Color.green())
            )

        emb = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.orange(), timestamp=datetime.utcnow())
        for w in warns:
            ts = int(datetime.fromisoformat(w['timestamp']).timestamp())
            emb.add_field(
                name=f"Warn #{w['id']} by {w.get('moderator_name', 'Unknown')}",
                value=f"Reason: {w['reason']} • <t:{ts}:R>",
                inline=False
            )
        await ctx.send(embed=emb)

    @warnings.command(name="clear", description="Clear a member's specific warning by ID")
    @commands.has_permissions(manage_messages=True)
    async def clear_warnings(self, ctx, member: discord.Member, warn_id: int):
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        warns = data["warnings"].get(guild_id, {}).get(user_id, [])
        found = None
        for w in list(warns):
            if w["id"] == warn_id:
                warns.remove(w)
                found = w
                break

        if not found:
            return await ctx.send(embed=discord.Embed(
                description=f"⚠️ Warning #{warn_id} not found for {member.mention}.",
                color=discord.Color.red())
            )

        # Reindex remaining warnings so IDs stay 1..n
        for i, w in enumerate(warns, start=1):
            w["id"] = i
        save_data(data)

        # If user is currently timed out, lift it
        undo_note = ""
        try:
            if member.is_timed_out():
                await member.edit(timed_out_until=None, reason="Warning cleared")
                data["timeouts"].pop(str(member.id), None)
                save_data(data)
                undo_note = " • Removed active timeout."
        except Exception:
            pass

        emb = discord.Embed(title="✅ Warning Cleared", color=discord.Color.green(), timestamp=datetime.utcnow())
        emb.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        emb.add_field(name="Cleared Warn #", value=str(warn_id), inline=True)
        emb.add_field(name="Original Reason", value=found['reason'], inline=False)
        if undo_note:
            emb.add_field(name="Action", value=undo_note.lstrip(" • "), inline=False)
        await ctx.send(embed=emb)

    # ---------------- Warn Punishment ----------------
    @commands.hybrid_command(name="warnpunishment", description="Configure punishment for a warn count")
    @commands.has_permissions(administrator=True)
    async def warnpunishment(self, ctx, count: int, action: str, mute_time: str = None):
        guild_id = str(ctx.guild.id)
        data["punishments"].setdefault(guild_id, {})

        norm = self.punishment_normalize(action)
        if not norm:
            return await ctx.send(embed=discord.Embed(
                description="❌ Invalid action. Use `mute`, `kick`, or `ban`.",
                color=discord.Color.red())
            )

        entry = {"action": norm}
        if norm == "Mute":
            if not mute_time:
                return await ctx.send(embed=discord.Embed(
                    description="❌ Mute requires a duration (e.g. `5m`, `1h`, `2d`, `1w`, `1mon`).",
                    color=discord.Color.red())
                )
            # Validate by parsing (store the original string)
            try:
                _ = self.parse_time(mute_time)
            except Exception:
                return await ctx.send(embed=discord.Embed(
                    description="❌ Invalid time format. Use like `5m`, `1h`, `2d`, `1w`, `1mon`.",
                    color=discord.Color.red())
                )
            entry["duration"] = mute_time

        data["punishments"][guild_id][str(count)] = entry
        save_data(data)

        emb = discord.Embed(title="⚙️ Punishment Configured", color=discord.Color.blurple(), timestamp=datetime.utcnow())
        emb.add_field(name="Warn Count", value=str(count), inline=True)
        emb.add_field(name="Action", value=entry['action'], inline=True)
        if entry['action'] == "Mute":
            emb.add_field(name="Duration", value=entry['duration'], inline=True)
        await ctx.send(embed=emb)

    # ---------------- Timeout Checker ----------------
    @tasks.loop(minutes=1)
    async def check_timeouts(self):
        now = datetime.utcnow()
        expired = []
        for user_id, info in list(data["timeouts"].items()):
            try:
                until = datetime.fromisoformat(info["until"])
            except Exception:
                expired.append(user_id)
                continue
            guild = self.bot.get_guild(int(info["guild"]))
            member = guild.get_member(int(user_id)) if guild else None

            if until <= now:
                if member:
                    try:
                        await member.edit(timed_out_until=None, reason="Timeout expired")
                    except Exception:
                        pass
                expired.append(user_id)

        for uid in expired:
            data["timeouts"].pop(uid, None)
        if expired:
            save_data(data)

async def setup(bot):
    await bot.add_cog(Warnings(bot))
