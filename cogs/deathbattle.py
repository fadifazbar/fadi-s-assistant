import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# Hardcoded emojis
BATTLE_EMOJI = "<:battle_emoji:1408620699349946572>"
WINNER_EMOJI = "<:Deathbattle_Winer_V2:1408667344682618951>"
DEATHBATTLE_EMOJI = "<:Deathbattle_V2:1408666286463914067>"
HEALTH_EMOJI = "<:HP_V2:1408669354069065748>"
CRITICAL_EMOJI = "<:CRITICAL_HIT:1408659817127612519>"
HEAL_EMOJI = "<:MENDING_HEART:1408664782005080094>"
GOLDEN_HEART = "<:GOLDEN_HEART:1408674925950144614>"
STUN_EMOJI = "<:stun:1409016286104518827>"
BURN_EMOJI = "<:burn:1409016476760936529>"
DODGE_EMOI = "<:dodge:1409016517970100325>"

# ✅ HP BAR FUNCTION
def hp_bar(hp: int, max_hp: int = 100) -> str:
    total_bars = 10
    if hp > 0:
        filled_bars = (hp * total_bars) // max_hp  # each 10 HP = 1 bar
    else:
        filled_bars = 0
    empty_bars = total_bars - filled_bars

    # Decide bar color
    if hp > 60:
        bar = "🟩" * filled_bars
    elif hp > 30:
        bar = "🟨" * filled_bars
    else:
        bar = "🟥" * filled_bars

    return bar + "⬛" * empty_bars + f"  ({hp} HP)"

class DeathBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash command
    @app_commands.command(name="deathbattle", description="Start a deathbattle between two players!")
    async def deathbattle_slash(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
        await self.start_battle(interaction, player1, player2)

    # Prefix command
    @commands.command(name="deathbattle")
    async def deathbattle_prefix(self, ctx, player1: discord.Member, player2: discord.Member):
        await self.start_battle(ctx, player1, player2)

    async def start_battle(self, ctx_or_interaction, player1, player2):
        # Detect ctx or interaction
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
        send = ctx_or_interaction.response.send_message if is_interaction else ctx_or_interaction.send

        # Initial stats
        hp1, hp2 = 100, 100
        turn = 1
        log = []
        full_log = []  # Keep the entire battle history for DM
        total_stats = {
            player1: {"damage": 0, "healing": 0},
            player2: {"damage": 0, "healing": 0}
        }

        # Track stun and burn
        stunned_players = {player1: False, player2: False}
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
            (21, 29,  "**__{attacker}__** used nostalgia on **__{defender}__** leading him to lose **__{dmg}__**.hp"),
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
            description=f"# {DEATHBATTLE_EMOJI} {player1.name} VS {player2.name} {DEATHBATTLE_EMOJI}\nFight begins!",
            color=discord.Color.red()
        )
    embed.add_field(
        name=player1.name,
        value=f"{hp_bar(hp1)}\n{HEALTH_EMOJI} {hp1}/100",
        inline=True
    )
    embed.add_field(
        name=player2.name,
        value=f"{hp_bar(hp2)}\n{HEALTH_EMOJI} {hp2}/100",
        inline=True
    )

        msg = await send(embed=embed)
        if is_interaction:
            msg = await ctx_or_interaction.original_response()

        await asyncio.sleep(2)

        # Fight loop
        while hp1 > 0 and hp2 > 0:
            attacker = player1 if turn % 2 != 0 else player2
            defender = player2 if turn % 2 != 0 else player1

            # Skip turn if stunned
            if stunned_players.get(attacker, False):
                skip_text = f"{STUN_EMOJI} **{attacker.name}** is stunned and misses their turn!"
                log.append((turn, skip_text))
                full_log.append(f"Turn {turn}: {skip_text}")
                if len(log) > 3:
                    log.pop(0)
                stunned_players[attacker] = False

                # Update embed
                embed.clear_fields()
                for t, entry in log:
                    embed.add_field(name=f"Turn {t}", value=entry, inline=False)
                embed.add_field(name=player1.name, value=hp_bar(hp1), inline=True)
                embed.add_field(name=player2.name, value=hp_bar(hp2), inline=True)
                await msg.edit(embed=embed)
                await asyncio.sleep(1.5)
                turn += 1
                continue

            # Apply burn damage if any
            if burn_damage_next_turn[attacker] > 0:
                burn_text = f"{BURN_EMOJI} **{attacker.name}** takes {burn_damage_next_turn[attacker]} burn damage!"
                if attacker == player1:
                    hp1 = max(0, hp1 - burn_damage_next_turn[attacker])
                else:
                    hp2 = max(0, hp2 - burn_damage_next_turn[attacker])
                log.append((turn, burn_text))
                full_log.append(f"Turn {turn}: {burn_text}")
                if len(log) > 3:
                    log.pop(0)
                burn_damage_next_turn[attacker] = 0

                embed.clear_fields()
                for t, entry in log:
                    embed.add_field(name=f"Turn {t}", value=entry, inline=False)
                embed.add_field(name=player1.name, value=hp_bar(hp1), inline=True)
                embed.add_field(name=player2.name, value=hp_bar(hp2), inline=True)
                await msg.edit(embed=embed)
                await asyncio.sleep(1.5)

            # 🩹 Healing chance (15%)
            if random.random() < 0.15:
                heal_amount = random.randint(5, 20)
                crit_heal = random.random() < 0.1
                if crit_heal:
                    heal_amount *= 2
                if attacker == player1:
                    hp1 = min(100, hp1 + heal_amount)
                else:
                    hp2 = min(100, hp2 + heal_amount)
                total_stats[attacker]["healing"] += heal_amount
                heal_text = f"{GOLDEN_HEART} **__{attacker.name}__** used the **Ultimate Golden Heart** and recovered __**{heal_amount} HP**__!" if crit_heal else f"{HEAL_EMOJI} **__{attacker.name}__** used a mending heart and recovered **{heal_amount} HP**!"
                log.append((turn, heal_text))
                full_log.append(f"Turn {turn}: {heal_text}")
                if len(log) > 3:
                    log.pop(0)

                embed.clear_fields()
                for t, entry in log:
                    embed.add_field(name=f"Turn {t}", value=entry, inline=False)
                embed.add_field(name=player1.name, value=hp_bar(hp1), inline=True)
                embed.add_field(name=player2.name, value=hp_bar(hp2), inline=True)
                await msg.edit(embed=embed)
                await asyncio.sleep(1.5)
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

            damage = chosen_dmg

            # Critical hit (10%)
            crit = random.random() < 0.1
            if crit:
                damage *= 2

            # Special mechanics
            dodge = random.random() < 0.1
            burn = random.random() < 0.05
            stun = random.random() < 0.05
            special_text = ""

            if dodge:
                damage = 0
                special_text += f"{DODGE_EMOI} **{defender.name}** dodged the attack!\n"
            if burn:
                burn_damage_next_turn[defender] = random.randint(5, 10)
                special_text += f"{BURN_EMOJI} **{defender.name}** is burned and will take {burn_damage_next_turn[defender]} damage next turn!\n"
            if stun:
                stunned_players[defender] = True
                special_text += f"{STUN_EMOJI} **{defender.name}** is stunned and will miss their next turn!\n"

            # Apply damage
            if defender == player1:
                hp1 = max(0, hp1 - damage)
            else:
                hp2 = max(0, hp2 - damage)

            total_stats[attacker]["damage"] += damage
            attack_text = f"{BATTLE_EMOJI} " + chosen_template.format(attacker=attacker.name, defender=defender.name, dmg=damage, chance=chosen_percent)
            if crit:
                attack_text += f" {CRITICAL_EMOJI} **CRITICAL HIT!**"
            attack_text += "\n" + special_text if special_text else ""

            log.append((turn, attack_text))
            full_log.append(f"Turn {turn}: {attack_text}")
            if len(log) > 3:
                log.pop(0)

            embed.clear_fields()
            for t, entry in log:
                embed.add_field(name=f"Turn {t}", value=entry, inline=False)
            embed.add_field(name=player1.name, value=hp_bar(hp1), inline=True)
            embed.add_field(name=player2.name, value=hp_bar(hp2), inline=True)
            await msg.edit(embed=embed)
            await asyncio.sleep(1.5)
            turn += 1

        # Winner section
        winner = player1 if hp1 > 0 else player2
        loser = player2 if winner == player1 else player1
        finishing_action = random.choice(["annihilated", "finished off", "destroyed", "ended", "humiliated"])
        finish_text = f"# {WINNER_EMOJI} {winner.name} {finishing_action} {loser.name} to claim victory!"
        embed = discord.Embed(
            title=f"{WINNER_EMOJI} {winner.name.upper()} WINS!!! {WINNER_EMOJI}",
            description=finish_text,
            color=discord.Color.gold()
        )
        embed.add_field(name=winner.name, value=hp_bar(hp1 if winner == player1 else hp2), inline=True)
        embed.add_field(name=loser.name, value=hp_bar(hp1 if loser == player1 else hp2), inline=True)

        # Button for logs
        view = discord.ui.View()
        async def send_log(interaction: discord.Interaction):
            try:
                chunk_size = 20
                for i in range(0, len(full_log), chunk_size):
                    chunk = full_log[i:i+chunk_size]
                    log_embed = discord.Embed(
                        title="📜 DeathBattle Log",
                        description=f"Turns {i+1} → {i+len(chunk)}",
                        color=discord.Color.purple()
                    )
                    for entry in chunk:
                        turn_num, text = entry.split(": ", 1)
                        log_embed.add_field(name=turn_num, value=text, inline=False)
                    await interaction.user.send(embed=log_embed)
                totals_text = (
                    f"**{player1.name}** → Damage: {total_stats[player1]['damage']} | Healing: {total_stats[player1]['healing']}\n"
                    f"**{player2.name}** → Damage: {total_stats[player2]['damage']} | Healing: {total_stats[player2]['healing']}"
                )
                totals_embed = discord.Embed(
                    title="📊 Final Battle Totals",
                    description=totals_text,
                    color=discord.Color.gold()
                )
                await interaction.user.send(embed=totals_embed)
                await interaction.response.send_message("📩 Check your DMs! Full battle log + totals sent as embeds.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ I couldn't DM you! Enable DMs from server members.", ephemeral=True)

        button = discord.ui.Button(label="📜 Get Full Battle Log", style=discord.ButtonStyle.blurple)
        button.callback = send_log
        view.add_item(button)
        await msg.edit(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
