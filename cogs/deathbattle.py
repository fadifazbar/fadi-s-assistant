import discord
from discord.ext import commands
from discord import app_commands
import random

class DeathBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Attacks system (add more attacks here)
        # Higher damage = rarer (lower weight)
        self.attacks = [
            {"name": "Punch 👊", "damage": 10, "weight": 40},
            {"name": "Kick 🦵", "damage": 15, "weight": 30},
            {"name": "Fireball 🔥", "damage": 25, "weight": 20},
            {"name": "Mega Blast 💥", "damage": 40, "weight": 8},
            {"name": "Ultimate Slash ⚔️", "damage": 60, "weight": 2},
        ]

    @app_commands.command(name="deathbattle", description="Start a deathbattle between two players!")
    async def deathbattle_slash(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
        await self.run_battle(interaction, player1, player2)

    async def run_battle(self, interaction, player1, player2):
        # Pick random attacks for each player
        p1_attack = random.choices(self.attacks, weights=[a["weight"] for a in self.attacks])[0]
        p2_attack = random.choices(self.attacks, weights=[a["weight"] for a in self.attacks])[0]

        p1_damage = p1_attack["damage"]
        p2_damage = p2_attack["damage"]

        # Decide winner (no ties)
        if p1_damage > p2_damage:
            winner, loser = player1, player2
            winner_attack, loser_attack = p1_attack, p2_attack
        elif p2_damage > p1_damage:
            winner, loser = player2, player1
            winner_attack, loser_attack = p2_attack, p1_attack
        else:
            # If exact same, force winner randomly
            winner, loser = random.choice([(player1, player2), (player2, player1)])
            winner_attack, loser_attack = (p1_attack, p2_attack) if winner == player1 else (p2_attack, p1_attack)

        # Fetch avatars
        p1_avatar = player1.display_avatar
        p2_avatar = player2.display_avatar

        # Create embed
        embed = discord.Embed(
            title="<:deathbattle:1408624946858426430> DeathBattle!",
            description=f"<:battle_emoji:1408620699349946572> **{player1.display_name}** vs **{player2.display_name}**\n\n"
                        f"**{player1.display_name}** used **{p1_attack['name']}** and dealt **{p1_damage}** damage!\n"
                        f"**{player2.display_name}** used **{p2_attack['name']}** and dealt **{p2_damage}** damage!\n\n"
                        f"<:deathbattle_winner:1408624915388563467> **Winner:** {winner.mention}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=winner.display_avatar.url)
        embed.set_image(url=p1_avatar.url if random.choice([True, False]) else p2_avatar.url)  # Randomly show one avatar big
        embed.set_footer(text="⚔️ Add more attacks in the list to expand battles!")

        # Send images + embed in one message
        files = [
            await p1_avatar.to_file(filename="p1.png"),
            await p2_avatar.to_file(filename="p2.png")
        ]
        embed.set_author(name="🔥 DeathBattle Results 🔥", icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(files=files, embed=embed)


async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
