import discord
from discord.ext import commands
from discord import app_commands
import random

# ---------------- Emojis ----------------
HP_EMOJI = "<:health_emoji:1408622054734958664>"
BATTLE_LOG_EMOJI = "<:deathbattle:1408624946858426430>"
WINNER_EMOJI = "<:deathbattle_winner:1408624915388563467>"
ATTACK_EMOJI = "<:battle_emoji:1408620699349946572>"

# ---------------- Attack Pool (damage, rarity) ----------------
attacks = [
    {"name": "Punch", "damage": 10, "weight": 50},
    {"name": "Kick", "damage": 15, "weight": 30},
    {"name": "Fireball", "damage": 20, "weight": 15},
    {"name": "Ultimate Smash", "damage": 35, "weight": 5},
]

class DeathBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------- Prefix Command --------
    @commands.command(name="deathbattle")
    async def deathbattle_prefix(self, ctx, player1: discord.Member, player2: discord.Member):
        await self.run_battle(ctx, player1, player2)

    # -------- Slash Command --------
    @app_commands.command(name="deathbattle", description="Start a death battle between two players!")
    async def deathbattle_slash(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
        await interaction.response.defer()
        await self.run_battle(interaction, player1, player2)

    # -------- Battle Logic --------
    async def run_battle(self, ctx_or_interaction, player1, player2):
        hp1 = 100
        hp2 = 100
        log = []

        # Pick first attacker randomly
        attacker, defender = (player1, player2) if random.choice([True, False]) else (player2, player1)
        hp_attacker, hp_defender = (hp1, hp2) if attacker == player1 else (hp2, hp1)

        # Embed Setup
        embed = discord.Embed(
            title=f"{BATTLE_LOG_EMOJI} Death Battle!",
            description=f"**{player1.name}** {HP_EMOJI} 100%  VS  **{player2.name}** {HP_EMOJI} 100%",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else discord.Embed.Empty)

        # Send initial embed
        if isinstance(ctx_or_interaction, commands.Context):
            message = await ctx_or_interaction.send(embed=embed)
        else:
            message = await ctx_or_interaction.followup.send(embed=embed, wait=True)

        # Battle Loop
        while hp1 > 0 and hp2 > 0:
            attack = random.choices(attacks, weights=[atk["weight"] for atk in attacks], k=1)[0]
            dmg = attack["damage"]

            if defender == player1:
                hp1 -= dmg
                if hp1 < 0:
                    hp1 = 0
            else:
                hp2 -= dmg
                if hp2 < 0:
                    hp2 = 0

            log.append(f"{ATTACK_EMOJI} **__{attacker.name}__** used **{attack['name']}** dealing **{dmg}%** damage!")

            # Update Embed
            embed.description = (
                f"**{player1.name}** {HP_EMOJI} {hp1}%  VS  **{player2.name}** {HP_EMOJI} {hp2}%\n\n"
                f"{BATTLE_LOG_EMOJI} **Battle Log:**\n" + "\n".join(log[-8:])
            )

            await message.edit(embed=embed)

            if hp1 <= 0 or hp2 <= 0:
                break

            # Switch turns
            attacker, defender = defender, attacker

        # Winner
        winner = player1 if hp1 > 0 else player2
        loser = player2 if winner == player1 else player1

        embed.description = (
            f"**{player1.name}** {HP_EMOJI} {hp1}%  VS  **{player2.name}** {HP_EMOJI} {hp2}%\n\n"
            f"{BATTLE_LOG_EMOJI} **Battle Log:**\n" + "\n".join(log[-8:]) +
            f"\n\n{WINNER_EMOJI} **__{winner.name}__ Wins!**"
        )
        embed.set_thumbnail(url=winner.avatar.url if winner.avatar else discord.Embed.Empty)
        await message.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
