import discord
from discord.ext import commands
from discord import app_commands
import random
from io import BytesIO

class DeathBattle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Prefix command
    @commands.command(name="deathbattle")
    async def deathbattle_prefix(self, ctx, player1: discord.Member, player2: discord.Member):
        await self.run_battle(ctx, player1, player2)

    # Slash command
    @app_commands.command(name="deathbattle", description="Start a deathbattle between two players")
    async def deathbattle_slash(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
        await self.run_battle(interaction, player1, player2)

    async def run_battle(self, ctx_or_inter, player1, player2):
        # Initial stats
        health = {player1: 100, player2: 100}
        log = []
        attacks = [
            ("shot", 5, 15),
            ("slapped", 1, 10),
            ("threw a bomb at", 20, 35),
            ("nuked", 30, 50),
        ]

        # Embed setup
        embed = discord.Embed(
            title="⚔️ Deathbattle ⚔️",
            description=f"<:deathbattle:1408624946858426430> **Battle Log:**\n",
            color=discord.Color.red()
        )

        embed.add_field(name=f"{player1.name}", value=f"<:health_emoji:1408622054734958664> {health[player1]}%", inline=True)
        embed.add_field(name=f"{player2.name}", value=f"<:health_emoji:1408622054734958664> {health[player2]}%", inline=True)

        # Prepare header image with pfps
        p1_avatar = player1.display_avatar.with_size(128)
        p2_avatar = player2.display_avatar.with_size(128)
        file = None

        # Send initial message
        if isinstance(ctx_or_inter, commands.Context):
            message = await ctx_or_inter.send(files=[await p1_avatar.to_file("p1.png"), await p2_avatar.to_file("p2.png")], embed=embed)
        else:
            message = await ctx_or_inter.response.send_message(files=[await p1_avatar.to_file("p1.png"), await p2_avatar.to_file("p2.png")], embed=embed)
            message = await ctx_or_inter.original_response()

        # Battle loop
        turn = 0
        while all(hp > 0 for hp in health.values()):
            attacker = player1 if turn % 2 == 0 else player2
            defender = player2 if turn % 2 == 0 else player1

            attack, min_dmg, max_dmg = random.choice(attacks)
            dmg = random.randint(min_dmg, max_dmg)
            health[defender] = max(0, health[defender] - dmg)

            # Add to log
            log.append(f"<:battle_emoji:1408620699349946572> __**{attacker.name}**__ {attack} __**{defender.name}**__ dealing **{dmg}** dmg!")
            if len(log) > 4:
                log.pop(0)

            # Update embed
            embed.clear_fields()
            embed.description = f"<:deathbattle:1408624946858426430> **Battle Log:**\n" + "\n".join(log)
            embed.add_field(name=f"{player1.name}", value=f"<:health_emoji:1408622054734958664> {health[player1]}%", inline=True)
            embed.add_field(name=f"{player2.name}", value=f"<:health_emoji:1408622054734958664> {health[player2]}%", inline=True)

            await message.edit(embed=embed)
            await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=2))
            turn += 1

        # Winner
        winner = player1 if health[player1] > 0 else player2
        embed.description += f"\n\n<:deathbattle_winner:1408624915388563467> __**{winner.name}**__ wins the Deathbattle!"
        await message.edit(embed=embed)

async def setup(bot):
    await bot.add_cog(DeathBattle(bot))
