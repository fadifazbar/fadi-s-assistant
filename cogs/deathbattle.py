import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image
import io
import aiohttp
import random
import asyncio
import os, json

LOG_FILE = "/data/deathbattle_logs.json"

# Hardcoded emojis (kept EXACTLY as provided)
BATTLE_EMOJI = "<:battle_emoji:1408620699349946572>"
WINNER_EMOJI = "<:Deathbattle_Winer_V2:1408667344682618951>"
DEATHBATTLE_EMOJI = "<:Deathbattle_V2:1408666286463914067>"
HEALTH_EMOJI = "<:HP_V2:1408669354069065748>"
CRITICAL_EMOJI = "<:CRITICAL_HIT:1408659817127612519>"
HEAL_EMOJI = "<:MENDING_HEART:1408664782005080094>"
GOLDEN_HEART = "<:Golden_Heart_V2:1408912627668750399>"
STUN_EMOJI = "<:stun:1409016286104518827>"
BURN_EMOJI = "<:burn:1409016476760936529>"
DODGE_EMOI = "<:dodge:1409016517970100325>"
POISON_EMOJI = "<:poison:1409341361488138240>"
FREEZE_EMOJI = "<:freeze:1409341385982742620>"
SHIELD_BREAK_EMOJI = "<:shield_break:1409341407461900318>"
LIFESTEAL_EMOJI = "<:life_steal:1409341445806231562>"
PARALYZE_EMOJI = "<:paralyze:1409341471403806720>"
EXPLOSION_EMOJI = "<:explosion:1409341495378575430>"
THORNS_EMOJI = "<:thorns:1409341564853026906>"
DOUBLE_STRIKE_EMOJI = "<:double_strike:1409341518434537494>"
CURSE_EMOJI = "<:curse:1409341540106506372>"

def save_log(message_id, full_log, total_stats, player1, player2):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    data[str(message_id)] = {
        "full_log": full_log,
        "total_stats": {
            str(player1.id): total_stats[player1],
            str(player2.id): total_stats[player2]
        },
        "players": {
            "p1": player1.id,
            "p2": player2.id
        }
    }

    with open(LOG_FILE, "w") as f:
        json.dump(data, f)

def load_log(message_id):
    if not os.path.exists(LOG_FILE):
        return None
    with open(LOG_FILE, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return None
    return data.get(str(message_id))



# ✅ HP BAR FUNCTION
def hp_bar(hp: int, max_hp: int) -> str:
    total_bars = 10
    if hp > 0:
        filled_bars = (hp * total_bars) // max_hp  # proportional to max_hp
        if filled_bars == 0:  # 👈 ensure at least 1 bar if hp > 0
            filled_bars = 1
    else:
        filled_bars = 0

    empty_bars = total_bars - filled_bars

    # Decide bar color
    if hp > max_hp * 0.6:
        bar = "🟩" * filled_bars
    elif hp > max_hp * 0.3:
        bar = "🟨" * filled_bars
    else:
        bar = "🟥" * filled_bars

    return bar + "⬛" * empty_bars + f"\n{HEALTH_EMOJI}  {hp}/{max_hp} Health"


# ✅ IMAGE GENERATION FUNCTION
async def create_battle_image(player1, player2):
    # Load player avatars
    async with aiohttp.ClientSession() as session:
        async with session.get(player1.display_avatar.url) as resp:
            avatar1_bytes = await resp.read()
        async with session.get(player2.display_avatar.url) as resp:
            avatar2_bytes = await resp.read()

        # Download background image
        background_url = "https://i.postimg.cc/G2nh3f9r/Picsart-25-08-25-02-44-59-583.jpg"
        async with session.get(background_url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to download background image: {resp.status}")
            background_bytes = await resp.read()

    avatar1 = Image.open(io.BytesIO(avatar1_bytes)).convert("RGBA")
    avatar2 = Image.open(io.BytesIO(avatar2_bytes)).convert("RGBA")

    # Resize avatars
    avatar1 = avatar1.resize((320, 320))
    avatar2 = avatar2.resize((320, 320))

    # Open background
    background = Image.open(io.BytesIO(background_bytes)).convert("RGBA")
    background = background.resize((1500, 500))  # adjust size if needed

    # Paste avatars
    background.paste(avatar1, (40, 90), avatar1)
    background.paste(avatar2, (1104, 90), avatar2)

    # Save to buffer
    buffer = io.BytesIO()
    background.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


class DeathBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash command
    @app_commands.command(name="deathbattle", description="Start a deathbattle between two players!")
    async def deathbattle_slash(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member, hp: int = 100):
        await self.start_battle(interaction, player1, player2, hp)

    # Prefix command
    @commands.command(name="deathbattle")
    async def deathbattle_prefix(self, ctx, player1: discord.Member, player2: discord.Member, hp: int = 100):
        await self.start_battle(ctx, player1, player2, hp)

    async def start_battle(self, ctx_or_interaction, player1, player2, hp: int = 100):
        # Detect ctx or interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
        send = ctx_or_interaction.response.send_message if is_interaction else ctx_or_interaction.send

        # Constants / initial stats
        max_hp = hp
        hp1, hp2 = max_hp, max_hp
        turn = 1
        log = []
        full_log = []  # Keep the entire battle history for DM
        total_stats = {
            player1: {"damage": 0, "healing": 0},
            player2: {"damage": 0, "healing": 0}
        }

        # Status trackers
        stunned_players = {player1: False, player2: False}   # skip exactly next turn
        frozen_players = {player1: False, player2: False}    # skip exactly next turn
        paralyzed_players = {player1: 0, player2: 0}         # N turns with 50% fail chance
        cursed_players = {player1: 0, player2: 0}            # N turns of halved damage when attacking
        poison_effects = {player1: 0, player2: 0}            # N turns remaining, 3 dmg per turn at start of their turn
        thorned_players = {player1: 0, player2: 0}           # N hits will reflect 3 dmg
        # (kept var name from your code, though not used for DOT here)
        burn_damage_next_turn = {player1: 0, player2: 0}

        # Attack actions (chance %, damage, template)
        attack_messages = [
            (40, 5,  "**__{attacker}__** slapped **__{defender}__** so hard that he farted dealing **__{dmg}__** damage"),
            (25, 10, "**__{attacker}__** punched **__{defender}__** straight in the face causing **__{dmg}__** damage"),
            (15, 15, "**__{attacker}__** kicked **__{defender}__** in the stomach for **__{dmg}__** damag"),
            (27, 19,  "**__{attacker}__** got freaky in bed with **__{defender}__** which led to sex making him lose **__{dmg}%__** of his virginity 🙏😭"),
            (10, 20, "**__{attacker}__** sliced **__{defender}'s__** body parts taking **__{dmg}__** damage out of him"),
            (5, 25,  "**__{attacker}__** stabbed **__{defender}__** violently dealing **__{dmg}__** damage"),
            (5, 30,  "**__{attacker}__** decapitated **__{defender}__** removing **__{dmg}__** hp from them"),
            (45, 4,  "**__{attacker}__** threw sand into **__{defender}'s__** eyes blinding them for **__{dmg}__** damage"),
            (2, 50,  "**__{defender}__** lost **__{dmg}__** because of**__{attacker}'s__** aura"),
            (19, 20,  "**__{attacker}__** dashes into **__{defender}__** breaking some of his bones and hr lost **__{dmg}__** hp"),
            (27, 27,  "**__{attacker}__** used a diamond sword on **__{defender}__** that does **__{dmg}__** damage"),
            (31, 0,  "**__{attacker}__** got scared from **__{defender}__** and dealt **__{dmg}__** damage"),
            (21, 29,  "**__{attacker}__** used nostalgia on **__{defender}__** leading him to lose **__{dmg}__** hp"),
            (13, 35,  "**__{attacker}__** brainwashed **__{defender}__** making him take away **__{dmg}__** hp from his hp bar"),
            (0.1, 10000,  "**__{attacker}__** became god and 1 shot **__{defender}__** (this is 0.1% to get.)"),
            (36, 12,  "**__{attacker}__** smashed **__{defender}__** with a hammer that delt **__{dmg}__** damage"),
            (38, 6,  "**__{attacker}__** spat at **__{defender}__**, grossing them out for **__{dmg}__** damage"),
            (33, 8,  "**__{attacker}__** tripped **__{defender}__**, scraping knees for **__{dmg}__** damage"),
            (29, 9,  "**__{attacker}__** bonked **__{defender}__** on the head with a stick causing **__{dmg}__** damage"),
            (26, 11, "**__{attacker}__** threw a chair at **__{defender}__** smashing for **__{dmg}__** damage"),
            (23, 13, "**__{attacker}__** broke a bottle over **__{defender}__**’s head for **__{dmg}__** damage"),
            (20, 15, "**__{attacker}__** suplexed **__{defender}__** into the ground, dealing **__{dmg}__** damage"),
            (19, 16, "**__{attacker}__** headbutted **__{defender}__** so hard they saw stars, taking **__{dmg}__** damage"),
            (18, 17, "**__{attacker}__** body-slammed **__{defender}__** for **__{dmg}__** damage"),
            (17, 18, "**__{attacker}__** used brass knuckles on **__{defender}__**, landing **__{dmg}__** damage"),
            (15, 20, "**__{attacker}__** pile-drove **__{defender}__** into the arena floor for **__{dmg}__** damage"),
            (14, 21, "**__{attacker}__** hurled a flaming bottle at **__{defender}__** burning for **__{dmg}__** damage"),
            (12, 23, "**__{attacker}__** cracked **__{defender}__**’s ribs with a baseball bat for **__{dmg}__** damage"),
            (10, 25, "**__{attacker}__** swung a steel pipe at **__{defender}__** breaking bones for **__{dmg}__** damage"),
            (8, 27,  "**__{attacker}__** electrocuted **__{defender}__** with a live wire for **__{dmg}__** damage"),
            (7, 30,  "**__{attacker}__** impaled **__{defender}__** with a spear dealing **__{dmg}__** damage"),
            (5, 33,  "**__{attacker}__** unleashed a savage uppercut launching **__{defender}__** for **__{dmg}__** damage"),
            (4, 36,  "**__{attacker}__** stomped **__{defender}__**’s skull mercilessly for **__{dmg}__** damage"),
            (3, 40,  "**__{attacker}__** dismembered **__{defender}__** with a brutal slash for **__{dmg}__** damage"),
            (2, 50,  "**__{attacker}__** unleashed a berserk rampage on **__{defender}__** dealing **__{dmg}__** damage"),
            (1, 75,  "**__{attacker}__** summoned a meteor onto **__{defender}__** crushing them for **__{dmg}__** damage"),
            (0.5, 500, "**__{attacker}__** called upon the ancient gods to smite **__{defender}__**, inflicting **__{dmg}__** damage"),
            (39, 5,  "**__{attacker}__** flicked **__{defender}__** on the forehead causing **__{dmg}__** damage"),
            (37, 7,  "**__{attacker}__** threw a shoe at **__{defender}__**, bonking for **__{dmg}__** damage"),
            (34, 9,  "**__{attacker}__** pushed **__{defender}__** down the stairs for **__{dmg}__** damage"),
            (32, 10, "**__{attacker}__** swung a frying pan into **__{defender}__**’s face for **__{dmg}__** damage"),
            (30, 11, "**__{attacker}__** launched a rock straight at **__{defender}__**’s skull causing **__{dmg}__** damage"),
            (28, 12, "**__{attacker}__** tackled **__{defender}__** through a table for **__{dmg}__** damage"),
            (27, 13, "**__{attacker}__** whipped **__{defender}__** with a chain causing **__{dmg}__** damage"),
            (25, 14, "**__{attacker}__** shoved a torch into **__{defender}__** burning them for **__{dmg}__** damage"),
            (24, 15, "**__{attacker}__** drop-elbowed **__{defender}__** into the ground for **__{dmg}__** damage"),
            (22, 16, "**__{attacker}__** broke a chair leg across **__{defender}__**’s back for **__{dmg}__** damage"),
            (20, 18, "**__{attacker}__** speared **__{defender}__** to the floor causing **__{dmg}__** damage"),
            (19, 19, "**__{attacker}__** swung a shovel into **__{defender}__** for **__{dmg}__** damage"),
            (17, 21, "**__{attacker}__** curb-stomped **__{defender}__** for **__{dmg}__** damage"),
            (16, 22, "**__{attacker}__** smashed a beer bottle into **__{defender}__**’s face for **__{dmg}__** damage"),
            (14, 24, "**__{attacker}__** wrapped barbed wire around their fist and punched **__{defender}__** for **__{dmg}__** damage"),
            (12, 26, "**__{attacker}__** exploded a firework in **__{defender}__**’s chest for **__{dmg}__** damage"),
            (10, 28, "**__{attacker}__** drove a knee into **__{defender}__**’s ribs breaking them for **__{dmg}__** damage"),
            (9, 30,  "**__{attacker}__** tore into **__{defender}__** with claws for **__{dmg}__** damage"),
            (7, 34,  "**__{attacker}__** slammed a boulder on **__{defender}__** crushing for **__{dmg}__** damage"),
            (6, 38,  "**__{attacker}__** impaled **__{defender}__** with an icicle dealing **__{dmg}__** damage"),
            (5, 42,  "**__{attacker}__** ripped part of the arena and smashed it onto **__{defender}__** for **__{dmg}__** damage"),
            (4, 48,  "**__{attacker}__** unleashed lightning down upon **__{defender}__** for **__{dmg}__** damage"),
            (3, 55,  "**__{attacker}__** summoned shadow hands to strangle **__{defender}__** for **__{dmg}__** damage"),
            (2, 70,  "**__{attacker}__** ripped **__{defender}__** apart in a gruesome strike dealing **__{dmg}__** damage"),
            (1, 100, "**__{attacker}__** unleashed an apocalyptic blast obliterating **__{defender}__** for **__{dmg}__** damage"),
        ]

        # Normalize %
        total_percent = sum(percent for percent, dmg, template in attack_messages)
        normalized = [(percent / total_percent, percent, dmg, template) for percent, dmg, template in attack_messages]

        embed = discord.Embed(
            title=f"{DEATHBATTLE_EMOJI} DEATHBATTLE {DEATHBATTLE_EMOJI}",
            description=(
                f"# {DEATHBATTLE_EMOJI} {player1.mention} VS {player2.mention} {DEATHBATTLE_EMOJI}\n"
                f"**__FIGHT BEGINS!!__**"
            ),
            color=discord.Color.red()
        )

        embed.add_field(name=player1.name, value=f"{hp_bar(hp1)}", inline=True)
        embed.add_field(name=player2.name, value=f"{hp_bar(hp2)}", inline=True)

        buffer = await create_battle_image(player1, player2)  # your BytesIO image
        file = discord.File(fp=buffer, filename="battle.png")



        
        msg = await send(embed=embed, file=file)
        if is_interaction:
            msg = await ctx_or_interaction.original_response()

        await asyncio.sleep(2)

        # Helper to push a log line and refresh the embed
        async def push_and_refresh(text: str):
            nonlocal embed, msg, log, full_log, hp1, hp2, turn
            log.append((turn, text))
            full_log.append(f"Turn {turn}: {text}")
            if len(log) > 3:
                log.pop(0)
            embed.clear_fields()
            for t, entry in log:
                embed.add_field(name=f"Turn {t}", value=entry, inline=False)
            embed.add_field(name=player1.name, value=hp_bar(hp1), inline=True)
            embed.add_field(name=player2.name, value=hp_bar(hp2), inline=True)
            await msg.edit(embed=embed)

        # Fight loop
        while hp1 > 0 and hp2 > 0:
            attacker = player1 if turn % 2 != 0 else player2
            defender = player2 if turn % 2 != 0 else player1

            # Apply start-of-turn poison on attacker
            if poison_effects[attacker] > 0 and (hp1 > 0 and hp2 > 0):
                if attacker == player1:
                    hp1 = max(0, hp1 - 3)
                else:
                    hp2 = max(0, hp2 - 3)
                poison_effects[attacker] -= 1
                await push_and_refresh(f"{POISON_EMOJI} **{attacker.name}** suffers **3** poison damage!")
                await asyncio.sleep(1.0)
                if hp1 == 0 or hp2 == 0:
                    break  # died to poison

            # Freeze / Stun checks (skip turn)
            if frozen_players.get(attacker, False):
                frozen_players[attacker] = False
                await push_and_refresh(f"{FREEZE_EMOJI} **{attacker.name}** is frozen and skips their turn!")
                await asyncio.sleep(1.2)
                turn += 1
                continue

            if stunned_players.get(attacker, False):
                stunned_players[attacker] = False
                await push_and_refresh(f"{STUN_EMOJI} **{attacker.name}** is stunned and misses their turn!")
                await asyncio.sleep(1.2)
                turn += 1
                continue

            # Paralyze (50% fail chance)
            if paralyzed_players.get(attacker, 0) > 0:
                paralyzed_players[attacker] -= 1
                if random.random() < 0.5:
                    await push_and_refresh(f"{PARALYZE_EMOJI} **{attacker.name}** is paralyzed and fails to act!")
                    await asyncio.sleep(1.2)
                    turn += 1
                    continue

            # Pick attack
            r = random.random()
            cumulative = 0
            chosen_template, chosen_percent, chosen_dmg = None, None, None
            for prob, percent, dmg, template in normalized:
                cumulative += prob
                if r <= cumulative:
                    chosen_template = template
                    chosen_percent = percent
                    chosen_dmg = dmg
                    break

            base_damage = chosen_dmg if chosen_dmg is not None else 0

            # Curse halves attacker's damage (if any)
            if cursed_players.get(attacker, 0) > 0:
                base_damage = int(base_damage / 2)
                cursed_players[attacker] -= 1

            # Critical hit (10%)
            crit = random.random() < 0.1
            if crit:
                base_damage *= 2

            special_text = ""

            # --- Mending Heart (heals instead of attacking) ---
            mending = random.random() < 0.05  # 5% chance
            if mending:
                heal = random.randint(10, 20)

                golden = random.random() < 0.02  # 2% chance
                if golden:
                    heal *= 2
                    special_text += f"{GOLDEN_HEART} __**{attacker.name}**__ unleashed the Golden Mending Heart and healed __**{heal}**__ HP!\n"
                else:
                    special_text += f"{HEAL_EMOJI} __**{attacker.name}**__ used Mending Heart and healed __**{heal}**__ HP!\n"

                if attacker == player1:
                    hp1 = min(max_hp, hp1 + heal)
                    total_stats[player1]["healing"] += heal
                else:
                    hp2 = min(max_hp, hp2 + heal)
                    total_stats[player2]["healing"] += heal

                # Log the healing and skip the attack completely
                await push_and_refresh(special_text.strip())
                await asyncio.sleep(1.5)
                turn += 1
                continue

            # Special mechanics (chance rolls)
            dodge = random.random() < 0.04        # 4% chance
            burn = random.random() < 0.03         # 3% chance
            stun = random.random() < 0.03         # 3% chance
            poison = random.random() < 0.025      # 2.5% chance
            freeze = random.random() < 0.02       # 2% chance
            shield_break = random.random() < 0.02 # 2% chance
            lifesteal = random.random() < 0.015   # 1.5% chance
            paralyze = random.random() < 0.015    # 1.5% chance
            explosion = random.random() < 0.01    # 1% chance
            double_strike = random.random() < 0.015 # 1.5% chance
            curse = random.random() < 0.01        # 1% chance
            thorns = random.random() < 0.015      # 1.5% chance

            # If defender dodges → no damage
            if dodge:
                base_damage = 0
                special_text += f"{DODGE_EMOI} __**{defender.name}**__ dodged __**{attacker.name}'s**__ attack!\n"

            # Burn (extra dmg same turn)
            burn_damage = 0
            if burn:
                burn_damage = random.randint(5, 10)
                special_text += f"{BURN_EMOJI} __**{defender.name}**__ is burned and suffers __**{burn_damage}**__ extra damage!\n"

            # Stun (skip next turn)
            if stun:
                stunned_players[defender] = True
                special_text += f"{STUN_EMOJI} __**{defender.name}**__ is stunned and will miss their next turn!\n"

            # Poison (3 dmg for 3 turns)
            if poison:
                poison_effects[defender] = 3
                special_text += f"{POISON_EMOJI} __**{defender.name}**__ is poisoned and will take 3 damage for 3 turns!\n"

            # Freeze (skip exactly one turn)
            if freeze:
                frozen_players[defender] = True
                special_text += f"{FREEZE_EMOJI} __**{defender.name}**__ is frozen solid and will skip their next turn!\n"

            # Shield Break (extra +5 dmg now)
            if shield_break:
                base_damage += 5
                special_text += f"{SHIELD_BREAK_EMOJI} __**{attacker.name}**__ shattered {defender.name}’s defenses for +5 dmg!\n"

            # Life Steal (drain HP instantly)
            if lifesteal:
                drain = 8
                if defender == player1:
                    hp1 = max(0, hp1 - drain)
                else:
                    hp2 = max(0, hp2 - drain)
                if attacker == player1:
                    hp1 = min(max_hp, hp1 + drain)
                else:
                    hp2 = min(max_hp, hp2 + drain)
                special_text += f"{LIFESTEAL_EMOJI} __**{attacker.name}**__ drains {drain} HP from {defender.name}!\n"

            # Paralyze (50% fail chance for 2 turns)
            if paralyze:
                paralyzed_players[defender] = 2
                special_text += f"{PARALYZE_EMOJI} __**{defender.name}**__ is paralyzed and may fail to act for 2 turns!\n"

            # Explosion (big dmg to both)
            if explosion:
                extra = 15
                self_dmg = 5
                if defender == player1:
                    hp1 = max(0, hp1 - extra)
                else:
                    hp2 = max(0, hp2 - extra)
                if attacker == player1:
                    hp1 = max(0, hp1 - self_dmg)
                else:
                    hp2 = max(0, hp2 - self_dmg)
                special_text += f"{EXPLOSION_EMOJI} __**{attacker.name}**__ exploded, dealing {extra} to {defender.name} and {self_dmg} to themselves!\n"

            # Double Strike (two small hits)
            extra_double = 0
            if double_strike:
                hit1 = random.randint(3, 6)
                hit2 = random.randint(2, 5)
                extra_double = hit1 + hit2
                special_text += f"{DOUBLE_STRIKE_EMOJI} __**{attacker.name}**__ strikes twice, hitting {hit1}+{hit2} for {extra_double} total!\n"

            # Curse (halve defender's damage for 2 turns)
            if curse:
                cursed_players[defender] = 2
                special_text += f"{CURSE_EMOJI} __**{defender.name}**__ is cursed! Their attacks deal half damage for 2 turns!\n"

            # Thorns (reflect 3 dmg for next 3 hits)
            if thorns:
                thorned_players[defender] = 3
                special_text += f"{THORNS_EMOJI} __**{defender.name}**__ grows thorns! Attacks against them reflect 3 damage for 3 hits.\n"

            # ✅ Apply total damage (base + burn + double-strike)
            total_damage = max(0, base_damage) + burn_damage + extra_double

            # Main attack line
            main_line = f"{BATTLE_EMOJI} {chosen_template.format(attacker=attacker.name, defender=defender.name, dmg=total_damage)}"
            if crit and total_damage > 0:
                main_line += f" {CRITICAL_EMOJI} **CRITICAL HIT!**"

            # Apply to defender
            if total_damage > 0:
                if defender == player1:
                    hp1 = max(0, hp1 - total_damage)
                else:
                    hp2 = max(0, hp2 - total_damage)

                # Thorns reflect if defender has thorns active
                if thorned_players.get(defender, 0) > 0:
                    thorn_dmg = 3
                    if attacker == player1:
                        hp1 = max(0, hp1 - thorn_dmg)
                    else:
                        hp2 = max(0, hp2 - thorn_dmg)
                    thorned_players[defender] -= 1
                    special_text += f"{THORNS_EMOJI} **{attacker.name}** is pricked by thorns and takes **{thorn_dmg}** reflected damage!\n"

            total_stats[attacker]["damage"] += total_damage

            # Compose and push turn log
            await push_and_refresh(f"{main_line}\n{special_text}".strip())
            await asyncio.sleep(1.5)

            # End if someone died
            if hp1 <= 0 or hp2 <= 0:
                break

            turn += 1


        # Winner section
        winner = player1 if hp1 > 0 else player2
        loser = player2 if winner == player1 else player1
        finishing_action = random.choice([
            "annihilated", "finished off", "destroyed", "ended", "humiliated", "obliterated", "eradicated", "crushed",
            "smashed", "terminated", "defeated", "wrecked", "ruined", "shattered", "demolished", "vanquished", "erased",
            "beaten", "trounced", "slain", "neutralized", "decimated", "flattened", "overpowered", "subdued", "leveled",
            "massacred", "slaughtered", "wiped out", "dismantled", "collapsed", "overthrown", "uprooted", "broken",
            "annexed", "smothered", "stomped", "snuffed out", "undone", "beheaded", "silenced", "overrun", "toppled",
            "axed", "liquidated", "extinguished", "deflated", "outclassed", "dethroned", "squashed", "wrecked beyond repair",
            "pulverized", "dominated", "ravaged", "trashed", "overwhelmed", "outmatched", "suffocated", "eradicated completely",
            "pummeled", "steamrolled", "humiliated utterly", "gutted", "dismembered", "wrecked utterly", "subjugated",
            "beaten down", "finished utterly", "torched", "ravished", "obliterated totally", "neutralized fully", "suppressed",
            "thrashed", "downtrodden", "laid waste", "cut down", "outdone", "snapped", "flattened completely", "taken apart",
            "rendered helpless", "beaten senseless", "dominated entirely", "reduced to nothing", "destroyed utterly",
            "eradicated fully", "pounded", "clobbered", "battered", "outstripped", "squelched", "terminated utterly",
            "sundered", "worn down", "left in ruins", "eliminated", "outshined", "obliterated brutally", "wrecked fully",
            "trampled", "beaten brutally", "leveled utterly", "finished mercilessly", "squashed flat"
        ])
        finish_text = f"# {WINNER_EMOJI} {winner.name} {finishing_action} {loser.name} to claim victory!"

        embed = discord.Embed(
            title=f"{WINNER_EMOJI} {winner.name.upper()} WINS!!! {WINNER_EMOJI}",
            description=finish_text,
            color=discord.Color.gold()
        )
        embed.add_field(
            name=winner.name,
            value=f"{hp_bar(hp1 if winner == player1 else hp2)}",
            inline=True
        )
        embed.add_field(
            name=loser.name,
            value=f"{hp_bar(hp1 if loser == player1 else hp2)}",
            inline=True
        )

        # ✅ Save the log here
        save_log(msg.id, full_log, total_stats, player1, player2)

        # Button for logs
        view = discord.ui.View()
        button = discord.ui.Button(label="📜 Get Full Battle Log", style=discord.ButtonStyle.blurple)
        button.callback = send_log
        view.add_item(button)

        
        await msg.edit(embed=embed, view=view)

async def send_log(interaction: discord.Interaction):
    data = load_log(interaction.message.id)
    if not data:
        await interaction.response.send_message("⚠️ Log not found (maybe purged after restart).", ephemeral=True)
        return

    full_log = data["full_log"]
    total_stats = data["total_stats"]
    p1_id, p2_id = data["players"]["p1"], data["players"]["p2"]

    player1 = interaction.client.get_user(p1_id)
    player2 = interaction.client.get_user(p2_id)

    try:
    chunk_size = 15  # smaller chunks to avoid hitting 6000 chars
    for i in range(0, len(full_log), chunk_size):
        chunk = full_log[i:i + chunk_size]
        log_embed = discord.Embed(
            title="📜 DeathBattle Log",
            description=f"Turns {i + 1} → {i + len(chunk)}",
            color=discord.Color.purple()
        )
        for entry in chunk:
            turn_num, text = entry.split(": ", 1)
            # truncate very long text
            if len(text) > 1000:
                text = text[:997] + "..."
            log_embed.add_field(name=turn_num, value=text, inline=False)
        await interaction.user.send(embed=log_embed)

        totals_text = (
            f"**{player1.name if player1 else 'Player 1'}** → "
            f"Damage: {total_stats[str(p1_id)]['damage']} | Healing: {total_stats[str(p1_id)]['healing']}\n"
            f"**{player2.name if player2 else 'Player 2'}** → "
            f"Damage: {total_stats[str(p2_id)]['damage']} | Healing: {total_stats[str(p2_id)]['healing']}"
        )
        totals_embed = discord.Embed(
            title="📊 Final Battle Totals",
            description=totals_text,
            color=discord.Color.gold()
        )
        await interaction.user.send(embed=totals_embed)
        await interaction.response.send_message("📩 Check your DMs! Full battle log + totals sent.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I couldn't DM you! Enable DMs from server members.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
