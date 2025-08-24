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
GOLDEN_HEART = "<:Golden_Heart_V2:1408912627668750399>"
STUN_EMOJI = "<:stun:1409016286104518827>"
BURN_EMOJI = "<:burn:1409016476760936529>"
DODGE_EMOI = "<:dodge:1409016517970100325>"

# ✅ HP BAR FUNCTION
def hp_bar(hp: int, max_hp: int = 100) -> str:
    total_bars = 10
    if hp > 0:
        filled_bars = (hp * total_bars) // max_hp  # each 10 HP = 1 bar
        if filled_bars == 0:  # 👈 ensure at least 1 bar if hp > 0
            filled_bars = 1
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

    return bar + "⬛" * empty_bars + f"\n{HEALTH_EMOJI}  {hp}/100 Health"
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

        embed.add_field(
            name=player1.name,
            value=f"{hp_bar(hp1)}",
            inline=True
        )
        embed.add_field(
            name=player2.name,
            value=f"{hp_bar(hp2)}",
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

            base_damage = chosen_dmg

            # Critical hit (10%)
            crit = random.random() < 0.1
            if crit:
                base_damage *= 2

            # Special mechanics
            dodge = random.random() < 0.04
            burn = random.random() < 0.03
            stun = random.random() < 0.03
            special_text = ""

            # If defender dodges → no damage
            if dodge:
                base_damage = 0
                special_text += f"{DODGE_EMOI} __**{defender.name}**__ dodged __**{attacker.name}'s**__ attack!\n"

            # If burn triggers → extra dmg added THIS turn
            burn_damage = 0
            if burn:
                burn_damage = random.randint(5, 10)
                special_text += f"{BURN_EMOJI} __**{defender.name}**__ is burned and suffers __**{burn_damage}**__ extra damage!\n"

            # If stun triggers → affects NEXT turn
            if stun:
                stunned_players[defender] = True
                special_text += f"{STUN_EMOJI} __**{defender.name}**__ is stunned and will miss their next turn!\n"

            # ✅ Apply total damage (base + burn)
            total_damage = base_damage + burn_damage
            if defender == player1:
                hp1 = max(0, hp1 - total_damage)
            else:
                hp2 = max(0, hp2 - total_damage)

            total_stats[attacker]["damage"] += total_damage

            # Build attack message
            attack_text = (
                f"{BATTLE_EMOJI} " +
                chosen_template.format(attacker=attacker.name, defender=defender.name, dmg=base_damage, chance=chosen_percent)
            )

            if burn_damage > 0:
                attack_text += f" (+__**{burn_damage}**__ burn dmg)"
            if crit:
                attack_text += f" {CRITICAL_EMOJI} **CRITICAL HIT!**"
            if special_text:
                attack_text += "\n" + special_text

            # Add to log
            log.append((turn, attack_text))
            full_log.append(f"Turn {turn}: {attack_text}")
            if len(log) > 3:
                log.pop(0)

            # Update embed
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
        finishing_action = random.choice(["annihilated", "finished off", "destroyed", "ended", "humiliated", "obliterated", "eradicated", "crushed", "smashed", "terminated", "defeated", "wrecked", "ruined", "shattered", "demolished", "vanquished", "erased", "beaten", "trounced", "slain", "neutralized", "decimated", "flattened", "overpowered", "subdued", "leveled", "massacred", "slaughtered", "wiped out", "dismantled", "collapsed", "overthrown", "uprooted", "broken", "annexed", "smothered", "stomped", "snuffed out", "undone", "beheaded", "silenced", "overrun", "toppled", "axed", "liquidated", "extinguished", "deflated", "outclassed", "dethroned", "squashed", "wrecked beyond repair", "pulverized", "dominated", "ravaged", "trashed", "overwhelmed", "outmatched", "suffocated", "eradicated completely", "pummeled", "steamrolled", "humiliated utterly", "gutted", "dismembered", "wrecked utterly", "subjugated", "beaten down", "finished utterly", "torched", "ravished", "obliterated totally", "neutralized fully", "suppressed", "thrashed", "downtrodden", "laid waste", "cut down", "outdone", "snapped", "flattened completely", "taken apart", "rendered helpless", "beaten senseless", "dominated entirely", "reduced to nothing", "destroyed utterly", "eradicated fully", "pounded", "clobbered", "battered", "outstripped", "squelched", "terminated utterly", "sundered", "worn down", "left in ruins", "eliminated", "outshined", "obliterated brutally", "wrecked fully", "trampled", "beaten brutally", "leveled utterly", "finished mercilessly", "squashed flat"])
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
