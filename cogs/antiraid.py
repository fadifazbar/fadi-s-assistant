# antinuke_full.py
# Full single-file anti-nuke + anti-raid system
# - Prefix and Slash commands
# - Per-guild persistent config saved to /data/antinuke_config.json (Railway safe)
# - Thresholds per action (limit + window seconds) + configurable punishment per action
# - Whitelist / Blacklist (add/remove/list) by ID (admins only)
# - Enable / Disable anti-nuke per guild
# - Owner-only ActionDmConfig toggles (which events DM the owner)
# - Admin-only config commands; non-admins see "You don't have the required permissions."
# - Full listeners: channel delete/create, role delete/create, emoji/sticker delete, member ban, member kick detection, webhook create
# - Uses audit logs to find executors and counts actions within windows
# - Auto-punish when thresholds exceeded
# - Dashboard command to show guild configuration

import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
import typing

# ---------------- Persistent File ----------------
DATA_DIR = "/data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
CONFIG_PATH = os.path.join(DATA_DIR, "security_config.json")

# fallback if /data not available locally
if not os.path.exists(CONFIG_PATH):
    # try local ./data
    local_dir = "./data"
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    CONFIG_PATH = os.path.join(local_dir, "antinuke_config.json")

# ---------------- Defaults ----------------
DEFAULT_THRESHOLDS = {
    # action_name: { "limit": int, "time": seconds, "punishment": "ban|kick|remove_roles|none" }
    "channel_delete": {"limit": 3, "time": 10, "punishment": "kick"},
    "channel_create": {"limit": 5, "time": 10, "punishment": "kick"},
    "role_delete": {"limit": 3, "time": 10, "punishment": "ban"},
    "role_create": {"limit": 5, "time": 10, "punishment": "kick"},
    "emoji_delete": {"limit": 5, "time": 30, "punishment": "ban"},
    "sticker_delete": {"limit": 5, "time": 30, "punishment": "ban"},
    "member_ban": {"limit": 3, "time": 15, "punishment": "ban"},
    "member_kick": {"limit": 4, "time": 15, "punishment": "ban"},
    "webhook_create": {"limit": 3, "time": 10, "punishment": "ban"},
    "member_join": {"limit": 12, "time": 10, "punishment": "lockdown"},  # join-raid
}

DEFAULT_ACTION_DM = {
    "config_change": True,
    "antinuke_trigger": True,
    "auto_lockdown": True,
    "manual_lockdown": True,
    "whitelist_change": True,
    "blacklist_change": True
}

DEFAULT_GUILD_CFG = {
    "enabled": True,
    "thresholds": DEFAULT_THRESHOLDS.copy(),
    "whitelist": [],    # list of IDs (integers)
    "blacklist": [],    # list of IDs (integers)
    "dm_config": DEFAULT_ACTION_DM.copy(),
    "violations": {},   # runtime persisted counts by user id -> action -> [iso timestamps]
    "lockdown": False
}

# ---------------- Utility: Load/Save ----------------
def load_all():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
    except Exception:
        pass
    # if file missing or bad, return empty dict
    return {}

def save_all(data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Failed to save config:", e)

# Load global config once
GLOBAL_CFG = load_all()

def ensure_guild_cfg(guild_id: int):
    gid = str(guild_id)
    if gid not in GLOBAL_CFG:
        GLOBAL_CFG[gid] = DEFAULT_GUILD_CFG.copy()
        # deep copy thresholds & dm_config to avoid shared refs
        GLOBAL_CFG[gid]["thresholds"] = json.loads(json.dumps(DEFAULT_THRESHOLDS))
        GLOBAL_CFG[gid]["dm_config"] = json.loads(json.dumps(DEFAULT_ACTION_DM))
        GLOBAL_CFG[gid]["whitelist"] = []
        GLOBAL_CFG[gid]["blacklist"] = []
        GLOBAL_CFG[gid]["violations"] = {}
        GLOBAL_CFG[gid]["lockdown"] = False
        save_all(GLOBAL_CFG)
    return GLOBAL_CFG[gid]

# ---------------- Runtime trackers ----------------
# trackers[guild_id][user_id][action] = deque([timestamps])
trackers = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: deque())))

# prune task to keep deques small
async def prune_once():
    now = datetime.utcnow().timestamp()
    for gid, users in list(trackers.items()):
        cfg = ensure_guild_cfg(int(gid))
        thresholds = cfg.get("thresholds", {})
        for uid, actions in list(users.items()):
            for action_name, dq in list(actions.items()):
                action_cfg = thresholds.get(action_name)
                if not action_cfg:
                    # default fallback window 10s
                    window = 10
                else:
                    window = int(action_cfg.get("time", 10))
                # pop left while too old
                while dq and (now - dq[0]) > window:
                    dq.popleft()

# helper to convert bool param parsing
def bool_from_str(s: typing.Union[str,bool]):
    if isinstance(s, bool):
        return s
    s = str(s).lower()
    return s in ("1","true","yes","on")

# ---------------- Bot setup ----------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)  # user earlier used various prefixes; using '!' here
tree = bot.tree

# ---------------- Permission check helper ----------------
def admin_check():
    def predicate(interaction_or_ctx):
        # allow invocation from slash (Interaction) or prefix (Context)
        if isinstance(interaction_or_ctx, discord.Interaction):
            member = interaction_or_ctx.user
            guild = interaction_or_ctx.guild
        else:
            member = interaction_or_ctx.author
            guild = interaction_or_ctx.guild
        if not guild:
            return False
        # owner is considered admin as well
        try:
            return member.guild_permissions.administrator or member.id == guild.owner_id
        except Exception:
            return False
    return commands.check(predicate)

# For slash commands: decorator wrapper to check admin and send friendly message
def admin_app_command(func):
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        member = interaction.user
        if not (member.guild_permissions.administrator or member.id == interaction.guild.owner_id):
            await interaction.response.send_message("❌ You don't have the required permissions.", ephemeral=True)
            return
        return await func(interaction, *args, **kwargs)
    return wrapper

# Error handler: for prefix command check failure -> friendly message
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ You don't have the required permissions.")
    else:
        # for debugging: print other errors
        # You can comment this out in prod
        print("Command error:", error)

# ---------------- Owner DM helper (uses per-guild dm_config) ----------------
async def dm_owner_if_allowed(guild: discord.Guild, key: str, text: str):
    cfg = ensure_guild_cfg(guild.id)
    dm_cfg = cfg.get("dm_config", DEFAULT_ACTION_DM)
    allowed = dm_cfg.get(key, True)
    if not allowed:
        return
    owner = guild.owner
    if not owner:
        return
    try:
        await owner.send(f"📢 **{key.replace('_',' ').title()}**\n{text}")
    except Exception:
        # if owner blocks DMs, fail silently
        pass

# ---------------- Violation logging & enforcement ----------------
def record_violation(guild_id: int, user_id: int, action_name: str):
    gid = str(guild_id)
    cfg = ensure_guild_cfg(guild_id)
    now_iso = datetime.utcnow().isoformat()
    viols = cfg.setdefault("violations", {})
    uviol = viols.setdefault(str(user_id), {})
    lst = uviol.setdefault(action_name, [])
    # remove old by window as well
    action_cfg = cfg.get("thresholds", {}).get(action_name, {})
    window = int(action_cfg.get("time", 10))
    cutoff = datetime.utcnow() - timedelta(seconds=window)
    # keep only timestamps newer than cutoff
    lst = [ts for ts in lst if datetime.fromisoformat(ts) > cutoff]
    lst.append(now_iso)
    uviol[action_name] = lst
    viols[str(user_id)] = uviol
    cfg["violations"] = viols
    save_all(GLOBAL_CFG)
    return len(lst)

async def enforce_if_needed(guild: discord.Guild, executor: discord.Member, action_name: str):
    cfg = ensure_guild_cfg(guild.id)
    tcfg = cfg.get("thresholds", {})
    action_cfg = tcfg.get(action_name)
    if not action_cfg:
        return
    count = record_violation(guild.id, executor.id, action_name)
    limit = int(action_cfg.get("limit", 3))
    punishment = action_cfg.get("punishment", "kick")
    if count >= limit:
        reason = f"Exceeded {action_name} threshold ({count}/{limit})"
        # apply punishment
        try:
            if punishment == "ban":
                await guild.ban(executor, reason=reason)
            elif punishment == "kick":
                await guild.kick(executor, reason=reason)
            elif punishment == "remove_roles":
                # remove all non-default roles
                roles_to_remove = [r for r in executor.roles if not r.is_default()]
                try:
                    await executor.remove_roles(*roles_to_remove, reason=reason)
                except Exception:
                    pass
            elif punishment == "lockdown":
                # set lockdown flag and set perms on channels
                cfg["lockdown"] = True
                save_all(GLOBAL_CFG)
                for ch in guild.text_channels:
                    ow = ch.overwrites_for(guild.default_role)
                    ow.send_messages = False
                    try:
                        await ch.set_permissions(guild.default_role, overwrite=ow, reason="Auto-lockdown triggered")
                    except Exception:
                        pass
                await dm_owner_if_allowed(guild, "auto_lockdown",
                    f"Auto-lockdown activated due to {action_name} by {executor} ({executor.id}). Reason: {reason}")
        except Exception:
            pass
        # notify owner per dm_config
        await dm_owner_if_allowed(guild, "antinuke_trigger",
            f"User {executor} ({executor.id}) punished with `{punishment}` for {action_name}. Reason: {reason}")
        # reset user's records for that action
        cfg = ensure_guild_cfg(guild.id)
        viols = cfg.get("violations", {})
        user_viol = viols.get(str(executor.id), {})
        user_viol[action_name] = []
        viols[str(executor.id)] = user_viol
        cfg["violations"] = viols
        save_all(GLOBAL_CFG)

# ---------------- Audit log helpers ----------------
async def get_audit_executor(guild: discord.Guild, action: discord.AuditLogAction, target_id: int = None, lookback_seconds: int = 5):
    """
    Returns (executor_member, audit_entry) if found, else (None, None).
    For actions with a target, tries to find the audit entry with the same target id within lookback_seconds.
    """
    try:
        async for entry in guild.audit_logs(limit=10, action=action):
            # If target_id is provided, match it when possible
            if target_id:
                if getattr(entry.target, "id", None) == target_id or str(getattr(entry.target, "id", None)) == str(target_id):
                    # ensure recent
                    if (datetime.utcnow() - entry.created_at).total_seconds() <= lookback_seconds:
                        return entry.user, entry
                else:
                    continue
            else:
                # no target to match: return the most recent entry if recent enough
                if (datetime.utcnow() - entry.created_at).total_seconds() <= lookback_seconds:
                    return entry.user, entry
        return None, None
    except Exception:
        return None, None

# ---------------- Listeners: full anti-nuke ----------------

@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    guild = channel.guild
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    # find who deleted it via audit logs
    executor, entry = await get_audit_executor(guild, discord.AuditLogAction.channel_delete, target_id=channel.id)
    if not executor:
        return
    # check whitelist/blacklist
    if executor.id in cfg.get("whitelist", []):
        return
    if executor.id in cfg.get("blacklist", []):
        # punish immediately as blacklisted
        try:
            await guild.ban(executor, reason="Blacklisted triggered channel delete")
        except Exception:
            pass
        await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} attempted channel delete and was banned.")
        return
    # record and enforce
    await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "channel_delete")

@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    guild = channel.guild
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    executor, entry = await get_audit_executor(guild, discord.AuditLogAction.channel_create)
    if not executor:
        return
    if executor.id in cfg.get("whitelist", []):
        return
    if executor.id in cfg.get("blacklist", []):
        try:
            await guild.ban(executor, reason="Blacklisted triggered channel create")
        except:
            pass
        await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} attempted channel create and was banned.")
        return
    await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "channel_create")

@bot.event
async def on_guild_role_delete(role: discord.Role):
    guild = role.guild
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    executor, entry = await get_audit_executor(guild, discord.AuditLogAction.role_delete, target_id=role.id)
    if not executor:
        return
    if executor.id in cfg.get("whitelist", []):
        return
    if executor.id in cfg.get("blacklist", []):
        try:
            await guild.ban(executor, reason="Blacklisted triggered role delete")
        except:
            pass
        await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} attempted role delete and was banned.")
        return
    await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "role_delete")

@bot.event
async def on_guild_role_create(role: discord.Role):
    guild = role.guild
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    executor, entry = await get_audit_executor(guild, discord.AuditLogAction.role_create)
    if not executor:
        return
    if executor.id in cfg.get("whitelist", []):
        return
    if executor.id in cfg.get("blacklist", []):
        try:
            await guild.ban(executor, reason="Blacklisted triggered role create")
        except:
            pass
        await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} attempted role create and was banned.")
        return
    await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "role_create")

@bot.event
async def on_guild_emojis_update(guild: discord.Guild, before, after):
    # deletion if len(after) < len(before)
    if len(after) >= len(before):
        return
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    # audit logs: emoji_delete
    try:
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.emoji_delete):
            executor = entry.user
            if executor.id in cfg.get("whitelist", []):
                return
            if executor.id in cfg.get("blacklist", []):
                try:
                    await guild.ban(executor, reason="Blacklisted triggered emoji delete")
                except:
                    pass
                await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} deleted emoji and was banned.")
                return
            await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "emoji_delete")
            break
    except Exception:
        return

@bot.event
async def on_guild_stickers_update(guild: discord.Guild, before, after):
    if len(after) >= len(before):
        return
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    try:
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.sticker_delete):
            executor = entry.user
            if executor.id in cfg.get("whitelist", []):
                return
            if executor.id in cfg.get("blacklist", []):
                try:
                    await guild.ban(executor, reason="Blacklisted triggered sticker delete")
                except:
                    pass
                await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} deleted sticker and was banned.")
                return
            await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "sticker_delete")
            break
    except Exception:
        return

@bot.event
async def on_webhooks_update(channel):
    # this event passes a TextChannel/Voice? doc shows `channel: abc.APIObject` but in discord.py it's the channel
    # treat as webhook create event occurred; check audit logs for webhook create
    guild = channel.guild
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    try:
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.webhook_create):
            executor = entry.user
            if executor.id in cfg.get("whitelist", []):
                return
            if executor.id in cfg.get("blacklist", []):
                try:
                    await guild.ban(executor, reason="Blacklisted triggered webhook create")
                except:
                    pass
                await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} created webhook and was banned.")
                return
            await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "webhook_create")
            break
    except Exception:
        return

@bot.event
async def on_member_ban(guild, user):
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    # find who banned via audit logs
    executor, entry = None, None
    try:
        executor, entry = await get_audit_executor(guild, discord.AuditLogAction.ban, target_id=user.id)
    except Exception:
        pass
    if not executor:
        return
    if executor.id in cfg.get("whitelist", []):
        return
    if executor.id in cfg.get("blacklist", []):
        try:
            await guild.ban(executor, reason="Blacklisted triggered ban action")
        except:
            pass
        await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} banned {user} and was banned.")
        return
    await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "member_ban")

@bot.event
async def on_member_remove(member):
    # member_remove triggers for leave or kick. Check audit logs whether a kick happened.
    guild = member.guild
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    try:
        executor, entry = await get_audit_executor(guild, discord.AuditLogAction.kick, target_id=member.id)
    except Exception:
        return
    if not executor:
        return
    if executor.id in cfg.get("whitelist", []):
        return
    if executor.id in cfg.get("blacklist", []):
        try:
            await guild.ban(executor, reason="Blacklisted triggered kick action")
        except:
            pass
        await dm_owner_if_allowed(guild, "blacklist_change", f"Blacklisted executor {executor} kicked {member} and was banned.")
        return
    await enforce_if_needed(guild, guild.get_member(executor.id) or executor, "member_kick")

# Member join (join-raid detection)
@bot.event
async def on_member_join(member):
    guild = member.guild
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("enabled", True):
        return
    # track join timestamps (store in cfg->violations under special key or in runtime tracker)
    gid = str(guild.id)
    # use runtime tracker for joins
    rt = trackers[gid]["__joins__"]
    now_ts = datetime.utcnow().timestamp()
    rt.append(now_ts)
    # prune older than window
    jc = cfg.get("thresholds", {}).get("member_join", {"limit":12,"time":10})
    window = int(jc.get("time", 10))
    limit = int(jc.get("limit", 12))
    while rt and (now_ts - rt[0]) > window:
        rt.popleft()
    if len(rt) >= limit:
        # trigger action against... joiners? Usually lock server
        punishment = jc.get("punishment", jc.get("punishment", "lockdown")) if isinstance(jc, dict) else "lockdown"
        # set lockdown
        cfg["lockdown"] = True
        save_all(GLOBAL_CFG)
        for ch in guild.text_channels:
            ow = ch.overwrites_for(guild.default_role)
            ow.send_messages = False
            try:
                await ch.set_permissions(guild.default_role, overwrite=ow, reason="Auto-lockdown triggered by join raid")
            except Exception:
                pass
        await dm_owner_if_allowed(guild, "auto_lockdown", f"Auto-lockdown activated: {len(rt)} joins in {window}s.")

# ---------------- Commands (prefix + slash equivalents) ----------------

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- utility command to show dashboard ----------
    @commands.command(name="security")
    @admin_check()
    @commands.guild_only()
    async def security_prefix(self, ctx):
        """Show current security dashboard"""
        cfg = ensure_guild_cfg(ctx.guild.id)
        embed = discord.Embed(title=f"Security Dashboard — {ctx.guild.name}", color=discord.Color.blue(), timestamp=datetime.utcnow())
        embed.add_field(name="Enabled", value=str(cfg.get("enabled", True)), inline=True)
        embed.add_field(name="Lockdown", value=str(cfg.get("lockdown", False)), inline=True)
        # thresholds summary
        th = cfg.get("thresholds", {})
        th_lines = []
        for k, v in th.items():
            th_lines.append(f"{k}: {v.get('limit')} per {v.get('time')}s → {v.get('punishment')}")
        embed.add_field(name="Thresholds", value="\n".join(th_lines) or "None", inline=False)
        embed.add_field(name="Whitelist (IDs)", value=", ".join(str(x) for x in cfg.get("whitelist", [])) or "None", inline=False)
        embed.add_field(name="Blacklist (IDs)", value=", ".join(str(x) for x in cfg.get("blacklist", [])) or "None", inline=False)
        await ctx.reply(embed=embed)

    @app_commands.command(name="security", description="Show security dashboard")
    @app_commands.default_permissions(administrator=True)
    async def security_slash(self, interaction: discord.Interaction):
        cfg = ensure_guild_cfg(interaction.guild.id)
        embed = discord.Embed(title=f"Security Dashboard — {interaction.guild.name}", color=discord.Color.blue(), timestamp=datetime.utcnow())
        embed.add_field(name="Enabled", value=str(cfg.get("enabled", True)), inline=True)
        embed.add_field(name="Lockdown", value=str(cfg.get("lockdown", False)), inline=True)
        th = cfg.get("thresholds", {})
        th_lines = []
        for k, v in th.items():
            th_lines.append(f"{k}: {v.get('limit')} per {v.get('time')}s → {v.get('punishment')}")
        embed.add_field(name="Thresholds", value="\n".join(th_lines) or "None", inline=False)
        embed.add_field(name="Whitelist (IDs)", value=", ".join(str(x) for x in cfg.get("whitelist", [])) or "None", inline=False)
        embed.add_field(name="Blacklist (IDs)", value=", ".join(str(x) for x in cfg.get("blacklist", [])) or "None", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- enable/disable antinuke ----------
    @commands.command(name="antinuke")
    @admin_check()
    @commands.guild_only()
    async def antinuke_prefix(self, ctx, mode: str):
        """Usage: !antinuke enable|disable"""
        cfg = ensure_guild_cfg(ctx.guild.id)
        if mode.lower() == "enable":
            cfg["enabled"] = True
            save_all(GLOBAL_CFG)
            await ctx.reply("✅ Anti-Nuke enabled")
            await dm_owner_if_allowed(ctx.guild, "config_change", f"Anti-Nuke enabled by {ctx.author} ({ctx.author.id})")
        elif mode.lower() == "disable":
            cfg["enabled"] = False
            save_all(GLOBAL_CFG)
            await ctx.reply("❌ Anti-Nuke disabled")
            await dm_owner_if_allowed(ctx.guild, "config_change", f"Anti-Nuke disabled by {ctx.author} ({ctx.author.id})")
        else:
            await ctx.reply("Usage: !antinuke enable | disable")

    @app_commands.command(name="antinuke", description="Enable or disable anti-nuke")
    @app_commands.describe(mode="enable or disable")
    @app_commands.default_permissions(administrator=True)
    async def antinuke_slash(self, interaction: discord.Interaction, mode: str):
        cfg = ensure_guild_cfg(interaction.guild.id)
        if mode.lower() == "enable":
            cfg["enabled"] = True
            save_all(GLOBAL_CFG)
            await interaction.response.send_message("✅ Anti-Nuke enabled", ephemeral=True)
            await dm_owner_if_allowed(interaction.guild, "config_change",
                f"Anti-Nuke enabled by {interaction.user} ({interaction.user.id})")
        elif mode.lower() == "disable":
            cfg["enabled"] = False
            save_all(GLOBAL_CFG)
            await interaction.response.send_message("❌ Anti-Nuke disabled", ephemeral=True)
            await dm_owner_if_allowed(interaction.guild, "config_change",
                f"Anti-Nuke disabled by {interaction.user} ({interaction.user.id})")
        else:
            await interaction.response.send_message("Usage: /antinuke <enable|disable>", ephemeral=True)

    # ---------- set threshold ----------
    @commands.command(name="setthreshold")
    @admin_check()
    @commands.guild_only()
    async def setthreshold_prefix(self, ctx, action: str, limit: int, time: int, punishment: str):
        """Usage: !setthreshold <action> <limit> <time_sec> <punishment>"""
        cfg = ensure_guild_cfg(ctx.guild.id)
        # validate punishment
        if punishment not in ("ban", "kick", "remove_roles", "lockdown", "none"):
            return await ctx.reply("Invalid punishment. Choose: ban, kick, remove_roles, lockdown, none")
        t = cfg.setdefault("thresholds", {})
        t[action] = {"limit": int(limit), "time": int(time), "punishment": punishment}
        save_all(GLOBAL_CFG)
        await ctx.reply(f"✅ Threshold set for `{action}`: {limit} per {time}s -> {punishment}")
        await dm_owner_if_allowed(ctx.guild, "config_change", f"Threshold changed by {ctx.author}: {action} -> {limit}/{time}s -> {punishment}")

    @app_commands.command(name="setthreshold", description="Set threshold for an action")
    @app_commands.describe(action="action name", limit="limit count", time="window seconds", punishment="ban|kick|remove_roles|lockdown|none")
    @app_commands.default_permissions(administrator=True)
    async def setthreshold_slash(self, interaction: discord.Interaction, action: str, limit: int, time: int, punishment: str):
        cfg = ensure_guild_cfg(interaction.guild.id)
        if punishment not in ("ban", "kick", "remove_roles", "lockdown", "none"):
            return await interaction.response.send_message("Invalid punishment.", ephemeral=True)
        t = cfg.setdefault("thresholds", {})
        t[action] = {"limit": int(limit), "time": int(time), "punishment": punishment}
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Threshold set for `{action}`: {limit} per {time}s -> {punishment}", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "config_change", f"Threshold changed by {interaction.user}: {action} -> {limit}/{time}s -> {punishment}")

    # ---------- whitelist add/remove/list (admin only) ----------
    @commands.group(name="whitelist", invoke_without_command=True)
    @admin_check()
    @commands.guild_only()
    async def whitelist_prefix(self, ctx):
        cfg = ensure_guild_cfg(ctx.guild.id)
        await ctx.reply("Whitelist: " + (", ".join(str(x) for x in cfg.get("whitelist", [])) or "None"))

    @whitelist_prefix.command(name="add")
    @admin_check()
    async def whitelist_add_prefix(self, ctx, id: int):
        cfg = ensure_guild_cfg(ctx.guild.id)
        if id in cfg.get("whitelist", []):
            return await ctx.reply("ID already whitelisted.")
        cfg["whitelist"].append(id)
        save_all(GLOBAL_CFG)
        await ctx.reply(f"✅ Added `{id}` to whitelist")
        await dm_owner_if_allowed(ctx.guild, "whitelist_change", f"{ctx.author} added {id} to whitelist")

    @whitelist_prefix.command(name="remove")
    @admin_check()
    async def whitelist_remove_prefix(self, ctx, id: int):
        cfg = ensure_guild_cfg(ctx.guild.id)
        if id not in cfg.get("whitelist", []):
            return await ctx.reply("ID not in whitelist.")
        cfg["whitelist"].remove(id)
        save_all(GLOBAL_CFG)
        await ctx.reply(f"❌ Removed `{id}` from whitelist")
        await dm_owner_if_allowed(ctx.guild, "whitelist_change", f"{ctx.author} removed {id} from whitelist")

    @app_commands.group(name="whitelist", description="Whitelist management", guild_only=True)
    @app_commands.default_permissions(administrator=True)
    async def whitelist_slash(self, interaction: discord.Interaction):
        # group placeholder; discord.py will not call this; subcommands defined below
        pass

    @whitelist_slash.command(name="add", description="Add ID to whitelist")
    @app_commands.describe(id="User or Bot ID")
    async def whitelist_slash_add(self, interaction: discord.Interaction, id: str):
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            return await interaction.response.send_message("❌ You don't have the required permissions.", ephemeral=True)
        try:
            iid = int(id)
        except:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)
        cfg = ensure_guild_cfg(interaction.guild.id)
        if iid in cfg.get("whitelist", []):
            return await interaction.response.send_message("ID already whitelisted.", ephemeral=True)
        cfg["whitelist"].append(iid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Added `{iid}` to whitelist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "whitelist_change", f"{interaction.user} added {iid} to whitelist")

    @whitelist_slash.command(name="remove", description="Remove ID from whitelist")
    @app_commands.describe(id="User or Bot ID")
    async def whitelist_slash_remove(self, interaction: discord.Interaction, id: str):
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            return await interaction.response.send_message("❌ You don't have the required permissions.", ephemeral=True)
        try:
            iid = int(id)
        except:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)
        cfg = ensure_guild_cfg(interaction.guild.id)
        if iid not in cfg.get("whitelist", []):
            return await interaction.response.send_message("ID not in whitelist.", ephemeral=True)
        cfg["whitelist"].remove(iid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"❌ Removed `{iid}` from whitelist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "whitelist_change", f"{interaction.user} removed {iid} from whitelist")

    # ---------- blacklist add/remove/list (admin only) ----------
    @commands.group(name="blacklist", invoke_without_command=True)
    @admin_check()
    @commands.guild_only()
    async def blacklist_prefix(self, ctx):
        cfg = ensure_guild_cfg(ctx.guild.id)
        await ctx.reply("Blacklist: " + (", ".join(str(x) for x in cfg.get("blacklist", [])) or "None"))

    @blacklist_prefix.command(name="add")
    @admin_check()
    async def blacklist_add_prefix(self, ctx, id: int):
        cfg = ensure_guild_cfg(ctx.guild.id)
        if id in cfg.get("blacklist", []):
            return await ctx.reply("ID already blacklisted.")
        cfg["blacklist"].append(id)
        save_all(GLOBAL_CFG)
        await ctx.reply(f"✅ Added `{id}` to blacklist")
        await dm_owner_if_allowed(ctx.guild, "blacklist_change", f"{ctx.author} added {id} to blacklist")

    @blacklist_prefix.command(name="remove")
    @admin_check()
    async def blacklist_remove_prefix(self, ctx, id: int):
        cfg = ensure_guild_cfg(ctx.guild.id)
        if id not in cfg.get("blacklist", []):
            return await ctx.reply("ID not in blacklist.")
        cfg["blacklist"].remove(id)
        save_all(GLOBAL_CFG)
        await ctx.reply(f"❌ Removed `{id}` from blacklist")
        await dm_owner_if_allowed(ctx.guild, "blacklist_change", f"{ctx.author} removed {id} from blacklist")

    @app_commands.group(name="blacklist", description="Blacklist management", guild_only=True)
    @app_commands.default_permissions(administrator=True)
    async def blacklist_slash(self, interaction: discord.Interaction):
        pass

    @blacklist_slash.command(name="add", description="Add ID to blacklist")
    @app_commands.describe(id="User/Bot ID")
    async def blacklist_slash_add(self, interaction: discord.Interaction, id: str):
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            return await interaction.response.send_message("❌ You don't have the required permissions.", ephemeral=True)
        try:
            iid = int(id)
        except:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)
        cfg = ensure_guild_cfg(interaction.guild.id)
        if iid in cfg.get("blacklist", []):
            return await interaction.response.send_message("ID already blacklisted.", ephemeral=True)
        cfg["blacklist"].append(iid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Added `{iid}` to blacklist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "blacklist_change", f"{interaction.user} added {iid} to blacklist")

    @blacklist_slash.command(name="remove", description="Remove ID from blacklist")
    @app_commands.describe(id="User/Bot ID")
    async def blacklist_slash_remove(self, interaction: discord.Interaction, id: str):
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            return await interaction.response.send_message("❌ You don't have the required permissions.", ephemeral=True)
        try:
            iid = int(id)
        except:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)
        cfg = ensure_guild_cfg(interaction.guild.id)
        if iid not in cfg.get("blacklist", []):
            return await interaction.response.send_message("ID not in blacklist.", ephemeral=True)
        cfg["blacklist"].remove(iid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"❌ Removed `{iid}` from blacklist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "blacklist_change", f"{interaction.user} removed {iid} from blacklist")

    # ---------- DM config (OWNER ONLY) ----------
    @commands.command(name="dmconfig")
    @commands.guild_only()
    async def dmconfig_prefix(self, ctx, key: str, value: bool):
        # only guild owner allowed
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply("❌ Only the server owner can change DM preferences.")
        cfg = ensure_guild_cfg(ctx.guild.id)
        if key not in cfg.get("dm_config", {}):
            return await ctx.reply(f"Unknown DM config key. Options: {', '.join(cfg.get('dm_config',{}).keys())}")
        cfg["dm_config"][key] = bool(value)
        save_all(GLOBAL_CFG)
        await ctx.reply(f"✅ Owner DM preference `{key}` set to `{value}`")

    @app_commands.command(name="dmconfig", description="Configure which events DM the server owner (owner only)")
    @app_commands.describe(key="dm config key", value="true or false")
    async def dmconfig_slash(self, interaction: discord.Interaction, key: str, value: bool):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Only the server owner can change DM preferences.", ephemeral=True)
        cfg = ensure_guild_cfg(interaction.guild.id)
        if key not in cfg.get("dm_config", {}):
            return await interaction.response.send_message(f"Unknown key. Options: {', '.join(cfg.get('dm_config',{}).keys())}", ephemeral=True)
        cfg["dm_config"][key] = bool(value)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Owner DM preference `{key}` set to `{value}`", ephemeral=True)

# ---------------- Setup cogs & background prune task ----------------

@tasks.loop(seconds=8)
async def _prune_task():
    await prune_once()

@bot.event
async def on_ready():
    # sync slash commands
    try:
        await bot.tree.sync()
    except Exception:
        pass
    if not _prune_task.is_running():
        _prune_task.start()

# add cog
bot.add_cog(AdminCog(bot))
bot.add_cog(commands.Cog())  # placeholder to keep structure (not required)

# ---------------- Run ----------------
# NOTE: user should set DISCORD_TOKEN in env
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("Missing DISCORD_TOKEN environment variable. Exiting.")
else:
    bot.run(TOKEN)
