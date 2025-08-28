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

# ---------------- DM Owner if Allowed ----------------
async def dm_owner_if_allowed(guild: discord.Guild, key: str, message: str):
    """
    Sends a DM to the guild owner if the guild's dm_config allows it.
    key: the config key in cfg["dm_config"] (e.g., "config_change")
    message: the text to send
    """
    cfg = ensure_guild_cfg(guild.id)
    if not cfg.get("dm_config", {}).get(key, False):
        return  # DM not allowed

    owner = guild.owner
    if not owner:
        return

    try:
        await owner.send(message)
    except Exception:
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

# Member join (join-raid detection + blacklisted/unverified bots)
@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    cfg = ensure_guild_cfg(guild.id)

    if not cfg.get("enabled", True):
        return

    # ---------------- Bot checks ----------------
    if member.bot:
        # Whitelist check
        if member.id in cfg.get("whitelist", []):
            print(f"Whitelisted bot joined: {member}")
            return

        # Kick if blacklisted
        if member.id in cfg.get("blacklist", []):
            try:
                fetched = await guild.fetch_member(member.id)
                await fetched.kick(reason="Blacklisted bot")
                print(f"Kicked blacklisted bot: {member}")
            except Exception as e:
                print(f"Failed to kick blacklisted bot: {member} -> {e}")
            return

        # Kick unverified bot and add to blacklist
        try:
            fetched = await guild.fetch_member(member.id)
            await fetched.kick(reason="Unverified bot auto-blacklisted")
            print(f"Added unverified bot to blacklist and kicked: {member}")
            cfg["blacklist"].append(member.id)
            save_all(GLOBAL_CFG)
            await dm_owner_if_allowed(
                guild,
                "blacklist_change",
                f"Unverified bot {member} auto-blacklisted and kicked"
            )
        except Exception as e:
            print(f"Failed to kick unverified bot: {member} -> {e}")
        return

    # ---------------- Join-raid detection ----------------
    gid = str(guild.id)
    rt = trackers[gid]["__joins__"]
    now_ts = datetime.utcnow().timestamp()
    rt.append(now_ts)

    jc = cfg.get("thresholds", {}).get("member_join", {"limit": 12, "time": 10})
    window = int(jc.get("time", 10))
    limit = int(jc.get("limit", 12))

    # prune older timestamps
    while rt and (now_ts - rt[0]) > window:
        rt.popleft()

    # trigger auto-lockdown if join-raid detected
    if len(rt) >= limit:
        punishment = jc.get("punishment", "lockdown")
        cfg["lockdown"] = True
        save_all(GLOBAL_CFG)

        for ch in guild.text_channels:
            ow = ch.overwrites_for(guild.default_role)
            ow.send_messages = False
            try:
                await ch.set_permissions(
                    guild.default_role,
                    overwrite=ow,
                    reason="Auto-lockdown triggered by join raid"
                )
            except Exception:
                pass

        await dm_owner_if_allowed(
            guild,
            "auto_lockdown",
            f"Auto-lockdown activated: {len(rt)} joins in {window}s."
        )


# ---------------- Commands (slash commands reworked) ----------------

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- Security Dashboard ----------
    @app_commands.command(name="security", description="Show security dashboard")
    @app_commands.default_permissions(administrator=True)
    async def security(self, interaction: discord.Interaction):
        cfg = ensure_guild_cfg(interaction.guild.id)
        embed = discord.Embed(
            title=f"Security Dashboard — {interaction.guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Enabled", value=str(cfg.get("enabled", True)), inline=True)
        embed.add_field(name="Lockdown", value=str(cfg.get("lockdown", False)), inline=True)
        th_lines = [f"{k}: {v.get('limit')} per {v.get('time')}s → {v.get('punishment')}" 
                    for k, v in cfg.get("thresholds", {}).items()]
        embed.add_field(name="Thresholds", value="\n".join(th_lines) or "None", inline=False)
        embed.add_field(name="Whitelist (IDs)", value=", ".join(str(x) for x in cfg.get("whitelist", [])) or "None", inline=False)
        embed.add_field(name="Blacklist (IDs)", value=", ".join(str(x) for x in cfg.get("blacklist", [])) or "None", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- Enable/Disable Anti-Nuke ----------
    @app_commands.command(name="antinuke", description="Enable or disable anti-nuke")
    @app_commands.describe(mode="Choose enable or disable")
    @app_commands.choices(mode=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable")
    ])
    @app_commands.default_permissions(administrator=True)
    async def antinuke(self, interaction: discord.Interaction, mode: str):
        cfg = ensure_guild_cfg(interaction.guild.id)
        cfg["enabled"] = mode == "enable"
        save_all(GLOBAL_CFG)
        msg = "✅ Anti-Nuke enabled" if cfg["enabled"] else "❌ Anti-Nuke disabled"
        await interaction.response.send_message(msg)
        await dm_owner_if_allowed(interaction.guild, "config_change", f"Anti-Nuke {mode}d by {interaction.user} ({interaction.user.id})")

    # ---------- Set Threshold ----------
    @app_commands.command(name="setthreshold", description="Set threshold for an action")
    @app_commands.describe(
        action="Action name",
        limit="Limit count",
        time="Window seconds",
        punishment="Type of punishment"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="channel_delete", value="channel_delete"),
            app_commands.Choice(name="channel_create", value="channel_create"),
            app_commands.Choice(name="role_delete", value="role_delete"),
            app_commands.Choice(name="role_create", value="role_create"),
            app_commands.Choice(name="emoji_delete", value="emoji_delete"),
            app_commands.Choice(name="sticker_delete", value="sticker_delete"),
            app_commands.Choice(name="member_ban", value="member_ban"),
            app_commands.Choice(name="member_kick", value="member_kick"),
            app_commands.Choice(name="webhook_create", value="webhook_create"),
            app_commands.Choice(name="member_join", value="member_join"),
        ]
    )
    @app_commands.choices(
        punishment=[
            app_commands.Choice(name="ban", value="ban"),
            app_commands.Choice(name="kick", value="kick"),
            app_commands.Choice(name="remove_roles", value="remove_roles"),
            app_commands.Choice(name="lockdown", value="lockdown"),
            app_commands.Choice(name="none", value="none")
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def setthreshold(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        limit: int,
        time: int,
        punishment: app_commands.Choice[str]
    ):
        cfg = ensure_guild_cfg(interaction.guild.id)
        cfg.setdefault("thresholds", {})[action.value] = {
            "limit": limit,
            "time": time,
            "punishment": punishment.value
        }
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(
            f"✅ Threshold set for `{action.value}`: {limit} per {time}s → {punishment.value}"
        )
        await dm_owner_if_allowed(
            interaction.guild,
            "config_change",
            f"Threshold changed by {interaction.user}: {action.value} → {limit}/{time}s → {punishment.value}"
        )


    # ---------- Whitelist ----------
    @app_commands.command(name="whitelist", description="Show or manage whitelist IDs")
    @app_commands.default_permissions(administrator=True)
    async def whitelist(self, interaction: discord.Interaction):
        cfg = ensure_guild_cfg(interaction.guild.id)
        await interaction.response.send_message("Whitelist: " + (", ".join(str(x) for x in cfg.get("whitelist", [])) or "None"), ephemeral=True)

    @app_commands.command(name="whitelist_add", description="Add user ID to whitelist")
    @app_commands.describe(user_id="User ID to whitelist (numbers only)")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_add(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Please provide a valid user ID (numbers only).", ephemeral=True
            )

        cfg = ensure_guild_cfg(interaction.guild.id)
        if uid in cfg.get("whitelist", []):
            return await interaction.response.send_message("User already whitelisted.", ephemeral=True)

        cfg["whitelist"].append(uid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Added `{uid}` to whitelist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "whitelist_change", f"{interaction.user} added `{uid}` to whitelist")


    @app_commands.command(name="whitelist_remove", description="Remove user ID from whitelist")
    @app_commands.describe(user_id="User ID to remove from whitelist (numbers only)")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_remove(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Please provide a valid user ID (numbers only).", ephemeral=True
            )

        cfg = ensure_guild_cfg(interaction.guild.id)
        if uid not in cfg.get("whitelist", []):
            return await interaction.response.send_message("User not in whitelist.", ephemeral=True)

        cfg["whitelist"].remove(uid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Removed `{uid}` from whitelist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "whitelist_change", f"{interaction.user} removed `{uid}` from whitelist")


    # ---------- Blacklist ----------
    @app_commands.command(name="blacklist", description="Show all blacklisted IDs")
    @app_commands.default_permissions(administrator=True)
    async def blacklist(self, interaction: discord.Interaction):
        cfg = ensure_guild_cfg(interaction.guild.id)
        await interaction.response.send_message(
            "Blacklist: " + (", ".join(str(x) for x in cfg.get("blacklist", [])) or "None"),
            ephemeral=True
        )

    @app_commands.command(name="blacklist_add", description="Add user ID to blacklist")
    @app_commands.describe(user_id="User ID to blacklist (numbers only)")
    @app_commands.default_permissions(administrator=True)
    async def blacklist_add(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Please provide a valid user ID (numbers only).", ephemeral=True
            )

        cfg = ensure_guild_cfg(interaction.guild.id)
        if uid in cfg.get("blacklist", []):
            return await interaction.response.send_message("User already blacklisted.", ephemeral=True)

        cfg["blacklist"].append(uid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Added `{uid}` to blacklist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "blacklist_change", f"{interaction.user} added `{uid}` to blacklist")


    @app_commands.command(name="blacklist_remove", description="Remove user ID from blacklist")
    @app_commands.describe(user_id="User ID to remove from blacklist (numbers only)")
    @app_commands.default_permissions(administrator=True)
    async def blacklist_remove(self, interaction: discord.Interaction, user_id: str):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Please provide a valid user ID (numbers only).", ephemeral=True
            )

        cfg = ensure_guild_cfg(interaction.guild.id)
        if uid not in cfg.get("blacklist", []):
            return await interaction.response.send_message("User not in blacklist.", ephemeral=True)

        cfg["blacklist"].remove(uid)
        save_all(GLOBAL_CFG)
        await interaction.response.send_message(f"✅ Removed `{uid}` from blacklist", ephemeral=True)
        await dm_owner_if_allowed(interaction.guild, "blacklist_change", f"{interaction.user} removed `{uid}` from blacklist")


# ---------------- Setup cogs & background prune task ----------------

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
