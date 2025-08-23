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

        # Attack actions (chance %, damage, template)
        attack_messages = [
            (40, 5,  "**__{attacker}__** slapped **__{defender}__** so hard that he farted dealing **__{dmg}__** dmg ({chance}%)"),
            (25, 10, "**__{attacker}__** punched **__{defender}__** straight in the face causing **__{dmg}__** dmg ({chance}%)"),
            (15, 15, "**__{attacker}__** kicked **__{defender}__** in the stomach for **__{dmg}__** dmg ({chance}%)"),
            (10, 20, "**__{attacker}__** sliced **__{defender}'s__** body parts taking **__{dmg}__** dmg out of him ({chance}%)"),
            (5, 25,  "**__{attacker}__** stabbed **__{defender}__** violently dealing **__{dmg}__** dmg ({chance}%)"),
            (5, 30,  "**__{attacker}__** decapitated **__{defender}__** leaving them with **__{dmg}__** dmg ({chance}%)"),
        ]

        # Normalize %
        total_percent = sum(percent for percent, dmg, template in attack_messages)
        normalized = [(percent / total_percent, percent, dmg, template) for percent, dmg, template in attack_messages]

        embed = discord.Embed(
            title=f"{DEATHBATTLE_EMOJI} DEATHBATTLE {DEATHBATTLE_EMOJI}",
            description=f"# {DEATHBATTLE_EMOJI} {player1.name} VS {player2.name} {DEATHBATTLE_EMOJI}\nFight begins!",
            color=discord.Color.red()
        )
        embed.add_field(name=player1.name, value=f"{HEALTH_EMOJI} {hp1}", inline=True)
        embed.add_field(name=player2.name, value=f"{HEALTH_EMOJI} {hp2}", inline=True)

        msg = await send(embed=embed)

        if is_interaction:
            msg = await ctx_or_interaction.original_response()

        await asyncio.sleep(2)

        # Fight loop
        while hp1 > 0 and hp2 > 0:
            attacker = player1 if turn % 2 != 0 else player2
            defender = player2 if turn % 2 != 0 else player1

# 🩹 Healing chance (15%)
        if random.random() < 0.15:
            heal_amount = random.randint(5, 20)

            # Critical heal (10%)
            crit_heal = random.random() < 0.1
            if crit_heal:
                heal_amount *= 2  # Double healing!

            if attacker == player1:
                hp1 = min(100, hp1 + heal_amount)
                if crit_heal:
                    heal_text = f"{GOLDEN_HEART} **__{attacker.name}__** used the **Ultimate Golden Heart** and recovered __**{heal_amount} HP**__! (Now at {hp1} HP)"
                else:
                    heal_text = f"{HEAL_EMOJI} **__{attacker.name}__** used a mending heart and recovered **{heal_amount} HP**! (Now at {hp1} HP)"
            else:
                hp2 = min(100, hp2 + heal_amount)
                if crit_heal:
                    heal_text = f"{GOLDEN_HEART} **__{attacker.name}__** used the **Ultimate Golden Heart** and recovered __**{heal_amount} HP**__! (Now at {hp2} HP)"
                else:
                    heal_text = f"{HEAL_EMOJI} **__{attacker.name}__** used a mending heart and recovered **{heal_amount} HP**! (Now at {hp2} HP)"

            log.append((turn, heal_text))
            if len(log) > 3:
                log.pop(0)

            # Update embed
            embed.clear_fields()
            for t, entry in log:
                embed.add_field(name=f"Turn {t}", value=entry, inline=False)

            embed.add_field(name=player1.name, value=f"{HEALTH_EMOJI} {hp1}", inline=True)
            embed.add_field(name=player2.name, value=f"{HEALTH_EMOJI} {hp2}", inline=True)

            await msg.edit(embed=embed)
            await asyncio.sleep(1.5)

            turn += 1
            continue  # Skip attack this turn

            # Pick attack style based on %
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

            # Apply damage
            if defender == player1:
                hp1 = max(0, hp1 - damage)
            else:
                hp2 = max(0, hp2 - damage)

            # Build full sentence
            attack_text = f"{BATTLE_EMOJI} " + chosen_template.format(
                attacker=attacker.name,
                defender=defender.name,
                dmg=damage,
                chance=chosen_percent
            )
            if crit:
                attack_text += f" {CRITICAL_EMOJI} **CRITICAL HIT!**"

            log.append((turn, attack_text))
            full_log.append(f"Turn {turn}: {attack_text}")
            if len(log) > 3:
                log.pop(0)

            # Update embed
            embed.clear_fields()

            # Show attack logs each on its own line
            for t, entry in log:
                embed.add_field(name=f"Turn {t}", value=entry, inline=False)

            # Add HP stats at bottom
            embed.add_field(name=player1.name, value=f"{HEALTH_EMOJI} {hp1}", inline=True)
            embed.add_field(name=player2.name, value=f"{HEALTH_EMOJI} {hp2}", inline=True)

            await msg.edit(embed=embed)
            await asyncio.sleep(1.5)

            turn += 1

        # Winner
        winner = player1 if hp1 > 0 else player2
        loser = player2 if winner == player1 else player1

        finishing_action = random.choice([
            "annihilated", "finished off", "destroyed", "ended", "humiliated"
        ])
        finish_text = f"# {WINNER_EMOJI} {winner.name} {finishing_action} {loser.name} to claim victory!"

        embed = discord.Embed(
            title=f"{WINNER_EMOJI} {winner.name.upper()} WINS!!! {WINNER_EMOJI}",
            description=finish_text,
            color=discord.Color.gold()
        )
        embed.add_field(name=winner.name, value=f"{HEALTH_EMOJI} {hp1 if winner == player1 else hp2}", inline=True)
        embed.add_field(name=loser.name, value=f"{HEALTH_EMOJI} {hp1 if loser == player1 else hp2}", inline=True)

        # Add button to request full log
        view = discord.ui.View()

        async def send_log(interaction: discord.Interaction):
            try:
                full_text = "\n".join(full_log)
                await interaction.user.send(f"📜 **Full DeathBattle Log:**\n{full_text}")
                await interaction.response.send_message("📩 Check your DMs!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ I couldn't DM you! Enable DMs from server members.", ephemeral=True)

        view.add_item(discord.ui.Button(label="📜 Get Full Battle Log", style=discord.ButtonStyle.blurple, custom_id="get_log"))

        async def button_callback(interaction: discord.Interaction):
            await send_log(interaction)

        view.children[0].callback = button_callback

        await msg.edit(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
