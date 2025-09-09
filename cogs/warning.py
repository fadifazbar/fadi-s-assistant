import discord
from typing import Optional
from discord.ext import commands, tasks
from discord import app_commands
import json, os, asyncio
from datetime import datetime, timedelta

import os, json

DATA_FILE = "/data/warns.json"  # Railway persistent volume

def load_data():
    if not os.path.exists(DATA_FILE):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump({"warnings": {}, "punishments": {}, "timeouts": {}}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
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
        if a in ("tempban", "temp ban"): return "TempBan"
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
        # ---------------- Role hierarchy checks ----------------
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(embed=discord.Embed(
                description=f"❌ You cannot warn {member.mention} because they have an equal or higher role than you.",
                color=discord.Color.red())
            )

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send(embed=discord.Embed(
                description=f"❌ I cannot warn {member.mention} because their top role is higher than or equal to my role.",
                color=discord.Color.red())
            )

        # ---------------- Normal warn logic ----------------
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

        # ---------------- Punishment checks ----------------
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
            elif action == "TempBan":
                if duration:
                    try:
                        seconds = self.parse_time(duration)
                        until = discord.utils.utcnow() + timedelta(seconds=seconds)

                        await member.ban(reason=f"Warn #{warn_number} punishment (tempban)")

                        # Save tempban info
                        data["timeouts"][str(member.id)] = {
                            "guild": guild_id,
                            "until": until.isoformat(),
                            "type": "tempban"
                        }
                        save_data(data)

                        action_taken_text = f"Banned for {duration}"
                        emb.add_field(name="Punishment", value=action_taken_text, inline=False)
                    except Exception as e:
                        emb.add_field(name="Punishment Error", value=f"Failed to tempban: `{e}`", inline=False)

                        
        await ctx.send(embed=emb)
        await self.dm_warned_user(member, ctx.guild, warn_number, reason, action_taken_text)


    # ---------------- Warnings Command ----------------
    @commands.hybrid_command(name="warnings", description="List warnings for a member")
    async def warnings(self, ctx, member: discord.Member):
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

    # ---------------- ClearWarn Command ----------------
    @commands.hybrid_command(name="clearwarn", description="Clear a member's warning(s)")
    @commands.has_permissions(manage_messages=True)
    async def clearwarn(self, ctx, member: discord.Member, warn_id: str):
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        warns = data["warnings"].get(guild_id, {}).get(user_id, [])
        if not warns:
            return await ctx.send(embed=discord.Embed(
                description=f"⚠️ {member.mention} has no warnings.",
                color=discord.Color.red())
            )

        # Case 1: Clear all warnings
        if warn_id.lower() == "all":
            cleared = len(warns)
            data["warnings"][guild_id][user_id] = []
            save_data(data)

            # Lift timeout if user is currently timed out
            undo_note = ""
            try:
                if member.is_timed_out():
                    await member.edit(timed_out_until=None, reason="All warnings cleared")
                    data["timeouts"].pop(str(member.id), None)
                    save_data(data)
                    undo_note = " • Removed active timeout."
            except Exception:
                pass

            emb = discord.Embed(title="✅ All Warnings Cleared", color=discord.Color.green(), timestamp=datetime.utcnow())
            emb.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
            emb.add_field(name="Warnings Removed", value=str(cleared), inline=True)
            if undo_note:
                emb.add_field(name="Action", value=undo_note.lstrip(" • "), inline=False)
            return await ctx.send(embed=emb)

        # Case 2: Clear one warning by ID
        try:
            warn_id = int(warn_id)
        except ValueError:
            return await ctx.send(embed=discord.Embed(
                description="⚠️ Please provide a valid warning ID or 'all'.",
                color=discord.Color.red())
            )

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

        # Reindex remaining warnings
        for i, w in enumerate(warns, start=1):
            w["id"] = i
        save_data(data)

        # Lift timeout if user is currently timed out
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
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Mute", value="mute"),
            app_commands.Choice(name="Kick", value="kick"),
            app_commands.Choice(name="Ban", value="ban"),
            app_commands.Choice(name="TempBan", value="tempban"),
        ]
    )
    async def warnpunishment(
        self,
        ctx: commands.Context,
        count: int,
        action: app_commands.Choice[str],
        mute_or_ban_time: Optional[str] = None
    ):
        guild_id = str(ctx.guild.id)

        norm = self.punishment_normalize(action.value)
        if not norm:
            return await ctx.send(embed=discord.Embed(
                description="❌ Invalid action. Use `mute`, `kick`, `ban`, or `tempban`.",
                color=discord.Color.red())
            )

        entry = {"action": norm}
        if norm in ("Mute", "TempBan"):
            if not mute_or_ban_time:
                return await ctx.send(embed=discord.Embed(
                    description="❌ This action requires a duration (e.g. `5m`, `1h`, `2d`, `1w`, `1mon`).",
                    color=discord.Color.red())
                )
            try:
                _ = self.parse_time(mute_or_ban_time)  # validate
            except Exception:
                return await ctx.send(embed=discord.Embed(
                    description="❌ Invalid time format. Use like `5m`, `1h`, `2d`, `1w`, `1mon`.",
                    color=discord.Color.red())
                )
            entry["duration"] = mute_or_ban_time

        data["punishments"].setdefault(guild_id, {})
        data["punishments"][guild_id][str(count)] = entry
        save_data(data)

        emb = discord.Embed(title="⚙️ Punishment Configured", color=discord.Color.blurple())
        emb.add_field(name="Warn Count", value=str(count), inline=True)
        emb.add_field(name="Action", value=entry['action'], inline=True)
        if "duration" in entry:
            emb.add_field(name="Duration", value=entry['duration'], inline=True)
        await ctx.send(embed=emb)

    # ---------------- Resume & Timeout Checker ----------------
    @tasks.loop(minutes=1)
    async def check_timeouts(self):
        now = datetime.utcnow()
        expired = []

        try:
            for user_id, info in list(data.get("timeouts", {}).items()):
                try:
                    until_str = info.get("until")
                    guild_id = info.get("guild")
                    ptype = info.get("type", "timeout")  # "timeout" (mute) or "tempban"

                    if not until_str or not guild_id:
                        logger.warning(f"check_timeouts: invalid entry for {user_id}: {info}")
                        expired.append(user_id)
                        continue

                    until = datetime.fromisoformat(until_str)
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        logger.warning(f"check_timeouts: guild {guild_id} not found for {user_id}")
                        expired.append(user_id)
                        continue

                    # ----------------- TIMEOUT/MUTE -----------------
                    if ptype == "timeout":
                        member = guild.get_member(int(user_id))

                        # Resume existing timeout if bot restarted
                        if member and not member.is_timed_out() and until > now:
                            try:
                                await member.edit(timed_out_until=until, reason="Resuming timeout after bot restart")
                            except Exception as e:
                                logger.exception(f"Failed to resume timeout for {user_id} in guild {guild_id}: {e}")

                        # Handle expiration
                        if until <= now:
                            if member:
                                try:
                                    await member.edit(timed_out_until=None, reason="Timeout expired")
                                except Exception as e:
                                    logger.exception(f"Failed to remove timeout for {user_id} in guild {guild_id}: {e}")
                            expired.append(user_id)

                    # ----------------- TEMPBAN -----------------
                    elif ptype == "tempban":
                        # if the time hasn't come yet, nothing to do
                        if until > now:
                            continue

                        # Time has come: try to unban
                        unbanned = False

                        # Strategy A: check current ban list and unban by BanEntry.user (most reliable)
                        try:
                            bans = await guild.bans()  # returns list of BanEntry
                            for ban_entry in bans:
                                if ban_entry.user.id == int(user_id):
                                    try:
                                        await guild.unban(ban_entry.user, reason="Tempban expired")
                                        logger.info(f"[auto-unban] Unbanned {user_id} from guild {guild_id} (found in ban list).")
                                        unbanned = True
                                    except Exception as e:
                                        logger.exception(f"[auto-unban] Failed to unban {user_id} via ban_entry.user: {e}")
                                    break
                        except Exception as e:
                            logger.exception(f"[auto-unban] Failed to fetch bans for guild {guild_id}: {e}")

                        # Strategy B (fallback): fetch user object and try to unban directly
                        if not unbanned:
                            try:
                                user_obj = await self.bot.fetch_user(int(user_id))
                                try:
                                    await guild.unban(user_obj, reason="Tempban expired")
                                    logger.info(f"[auto-unban] Unbanned {user_id} from guild {guild_id} (fetch_user fallback).")
                                    unbanned = True
                                except discord.NotFound:
                                    logger.info(f"[auto-unban] User {user_id} not in ban list for guild {guild_id}.")
                                except Exception as e:
                                    logger.exception(f"[auto-unban] Failed to unban {user_id} via fetch_user fallback: {e}")
                            except Exception as e:
                                logger.exception(f"[auto-unban] Failed to fetch user {user_id}: {e}")

                        # Regardless of success/failure, remove the entry (avoid loops)
                        expired.append(user_id)
                        if unbanned:
                            # optional: you can notify a mod-channel here if you want
                            pass

                    else:
                        # Unknown type -> clean up to avoid stalling
                        logger.warning(f"check_timeouts: unknown type '{ptype}' for {user_id} in guild {guild_id}")
                        expired.append(user_id)

                except Exception as e:
                    logger.exception(f"check_timeouts: error handling entry {user_id}: {e}")
                    expired.append(user_id)

        except Exception as e:
            logger.exception(f"check_timeouts: fatal loop error: {e}")

        # cleanup expired entries and persist once
        for uid in expired:
            data.get("timeouts", {}).pop(uid, None)

        if expired:
            try:
                save_data(data)
            except Exception as e:
                logger.exception(f"check_timeouts: failed to save data after cleanup: {e}")

    
    @check_timeouts.before_loop
    async def before_check_timeouts(self):
        # Wait until bot is ready
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Warnings(bot))
