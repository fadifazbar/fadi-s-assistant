import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# Emojis
HEALTH_EMOJI = "<:health_emoji:1408622054734958664>"
DEATH_EMOJI = "<:deathbattle:1408624946858426430>"
WINNER_EMOJI = "<:deathbattle_winner:1408624915388563467>"
BATTLE_EMOJI = "<:battle_emoji:1408620699349946572>"

# Attack list with rarity (weight = lower means rarer)
ATTACKS = [
    {"name": "punched", "damage": 10, "weight": 10},
    {"name": "slapped", "damage": 8, "weight": 12},
    {"name": "kicked", "damage": 12, "weight": 8},
    {"name": "headbutted", "damage": 15, "weight": 5},
    {"name": "dropkicked", "damage": 20, "weight": 3},
    {"name": "unleashed a mega blast on", "damage": 25, "weight": 1},
]

def pick_attack():
    return random.choices(ATTACKS, weights=[a["weight"] for a in ATTACKS], k=1)[0]

class DeathBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def run_battle(self, interaction, player1, player2):
        hp1, hp2 = 100, 100
        logs = []  # store last 3 actions

        # Intro message
        intro_embed = discord.Embed(
            title=f"{DEATH_EMOJI} Death Battle:",
            description=f"{player1.name} vs {player2.name}",
            color=discord.Color.red()
        )
        msg = await interaction.response.send_message(embed=intro_embed)
        await asyncio.sleep(5)

        while hp1 > 0 and hp2 > 0:
            attacker, defender = (player1, player2) if random.choice([True, False]) else (player2, player1)
            attack = pick_attack()

            # Critical hit check
            crit = random.random() < 0.2
            damage = attack["damage"] * (2 if crit else 1)

            if defender == player1:
                hp1 = max(0, hp1 - damage)
            else:
                hp2 = max(0, hp2 - damage)

            # Attack log line
            if crit:
                line = f"**CRITICAL HIT!** {attacker.name} {attack['name']} {defender.name} for {damage} damage!"
            else:
                line = f"{attacker.name} {attack['name']} {defender.name} for {damage} damage!"

            logs.append(line)
            if len(logs) > 3:
                logs.pop(0)

            # Health display
            health_display = (
                f"{player1.name} {HEALTH_EMOJI} {hp1}\n"
                f"{player2.name} {HEALTH_EMOJI} {hp2}\n\n"
                f"{BATTLE_EMOJI} Battle Log:\n" + "\n".join(logs)
            )

            battle_embed = discord.Embed(
                title=f"{DEATH_EMOJI} Death Battle",
                description=health_display,
                color=discord.Color.orange()
            )

            await msg.edit(embed=battle_embed)
            await asyncio.sleep(1.5)

        # Winner message
        winner = player1 if hp1 > 0 else player2
        win_embed = discord.Embed(
            title=f"{WINNER_EMOJI} {winner.name} WINS!!!",
            color=discord.Color.gold()
        )
        await msg.edit(embed=win_embed)

    # Prefix command
    @commands.command(name="deathbattle")
    async def deathbattle_prefix(self, ctx, user1: discord.Member, user2: discord.Member):
        await self.run_battle(ctx, user1, user2)

    # Slash command
    @app_commands.command(name="deathbattle", description="Start a death battle between two players")
    async def deathbattle_slash(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        await self.run_battle(interaction, user1, user2)


async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
