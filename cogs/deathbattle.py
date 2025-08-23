import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# Hardcoded emojis
BATTLE_EMOJI = "<:battle_emoji:1408620699349946572>"
WINNER_EMOJI = "<:deathbattle_winner:1408624915388563467>"
DEATHBATTLE_EMOJI = "<:deathbattle:1408624946858426430>"
HEALTH_EMOJI = "<:health_emoji:1408622054734958664>"

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

        # Attack actions (with rarity weights)
        attack_messages = [
            ("slapped", 40),        # very common
            ("punched", 30),
            ("kicked", 25),
            ("sliced", 20),
            ("stabbed", 15),
            ("blasted", 10),
            ("obliterated", 5),     # rare
            ("decapitated", 2)      # super rare
        ]
        actions, weights_actions = zip(*attack_messages)

        embed = discord.Embed(
            title=f"{DEATHBATTLE_EMOJI} DEATHBATTLE {DEATHBATTLE_EMOJI}",
            description=f"{player1.name} VS {player2.name}\nFight begins!",
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

            # Damage calculation with rarity weighting
            damage_values = [5, 10, 15, 20, 25]
            weights = [40, 30, 15, 10, 5]  # weaker = more common
            damage = random.choices(damage_values, weights=weights, k=1)[0]

            # Critical hit (10% chance, doubles damage)
            crit = random.random() < 0.1
            if crit:
                damage *= 2

            # Apply damage
            if defender == player1:
                hp1 = max(0, hp1 - damage)
            else:
                hp2 = max(0, hp2 - damage)

            # Pick a random attack style
            action = random.choices(actions, weights=weights_actions, k=1)[0]

            # Build attack message
            attack_text = f"{BATTLE_EMOJI} {attacker.name} {action} {defender.name} for **{damage}** damage!"
            if crit:
                attack_text += " 💥 **CRITICAL HIT!**"

            log.append(attack_text)
            if len(log) > 3:  # keep only last 3 visible
                log.pop(0)

            # Update embed
            embed.clear_fields()
            embed.description = "\n".join(log)
            embed.add_field(name=player1.name, value=f"{HEALTH_EMOJI} {hp1}", inline=True)
            embed.add_field(name=player2.name, value=f"{HEALTH_EMOJI} {hp2}", inline=True)

            await msg.edit(embed=embed)
            await asyncio.sleep(1.5)

            turn += 1

        # Winner
        winner = player1 if hp1 > 0 else player2
        loser = player2 if winner == player1 else player1

        # Special finishing message
        finishing_action = random.choice(["annihilated", "finished off", "destroyed", "ended"])
        finish_text = f"{winner.name} {finishing_action} {loser.name} to claim victory!"

        embed = discord.Embed(
            title=f"{WINNER_EMOJI} #{winner.name.upper()} WINS!!! {WINNER_EMOJI}",
            description=finish_text,
            color=discord.Color.gold()
        )
        embed.add_field(name=winner.name, value=f"{HEALTH_EMOJI} {hp1 if winner == player1 else hp2}", inline=True)
        embed.add_field(name=loser.name, value=f"{HEALTH_EMOJI} {hp1 if loser == player1 else hp2}", inline=True)

        await msg.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
