import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToe = self.view
        if interaction.user != view.current_player:
            return await interaction.response.send_message("It’s not your turn!", ephemeral=True)

        if view.board[self.y][self.x] != 0:
            return await interaction.response.send_message("That spot is already taken!", ephemeral=True)

        value = 1 if view.current_player == view.player1 else 2
        view.board[self.y][self.x] = value

        self.style = discord.ButtonStyle.danger if value == 1 else discord.ButtonStyle.success
        self.label = "❌" if value == 1 else "⭕"
        self.disabled = True

        winner = view.check_winner()
        if winner is not None:
            if winner == -1:
                text = "It’s a tie! 🤝"
                color = discord.Color.greyple()
            else:
                text = f"{interaction.user.mention} wins! 🎉"
                color = discord.Color.red() if winner == 1 else discord.Color.green()

            embed = discord.Embed(title="Tic-Tac-Toe", description=text, color=color)
            await interaction.response.edit_message(embed=embed, view=view.disable_all())
            view.cog.active_games.pop(view.message.channel.id, None)
            view.stop()
            return

        view.switch_turn()
        await view.update_message(interaction)


class TicTacToe(discord.ui.View):
    def __init__(self, cog, ctx, player1, player2):
        super().__init__(timeout=None)
        self.cog = cog
        self.ctx = ctx
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.board = [[0] * 3 for _ in range(3)]
        self.message = None
        self.last_move = asyncio.get_event_loop().time()

        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

        self.check_inactivity.start()

    def switch_turn(self):
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1
        self.last_move = asyncio.get_event_loop().time()

    async def update_message(self, interaction=None):
        color = discord.Color.red() if self.current_player == self.player1 else discord.Color.green()
        embed = discord.Embed(
            title="Tic-Tac-Toe",
            description=f"It’s {self.current_player.mention}'s turn! ({'❌' if self.current_player == self.player1 else '⭕'})",
            color=color
        )
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.message.edit(embed=embed, view=self)

    def check_winner(self):
        for row in self.board:
            if row[0] == row[1] == row[2] != 0:
                return row[0]
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != 0:
                return self.board[0][col]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != 0:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != 0:
            return self.board[0][2]
        if all(self.board[y][x] != 0 for y in range(3) for x in range(3)):
            return -1
        return None

    def disable_all(self):
        for item in self.children:
            item.disabled = True
        return self

    @tasks.loop(seconds=30)
    async def check_inactivity(self):
        if self.message and (asyncio.get_event_loop().time() - self.last_move > 180):  # 3 mins
            embed = discord.Embed(
                title="Tic-Tac-Toe",
                description="Game ended due to inactivity. ⏳",
                color=discord.Color.greyple()
            )
            await self.message.edit(embed=embed, view=self.disable_all())
            self.cog.active_games.pop(self.message.channel.id, None)
            self.stop()

    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="Tic-Tac-Toe",
                description="Game timed out. ⌛",
                color=discord.Color.greyple()
            )
            await self.message.edit(embed=embed, view=self.disable_all())
            self.cog.active_games.pop(self.message.channel.id, None)


class TicTacToeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}  # channel_id -> view

    @commands.command(name="tictactoe")
    async def tictactoe_command(self, ctx, opponent: discord.Member):
        """Play Tic-Tac-Toe with someone (prefix command)."""
        if ctx.channel.id in self.active_games:
            return await ctx.send("A game is already running in this channel!")

        view = TicTacToe(self, ctx, ctx.author, opponent)
        embed = discord.Embed(
            title="❌ Tic-Tac-Toe ⭕",
            description=f"{ctx.author.mention} vs {opponent.mention}\nIt’s {ctx.author.mention}'s turn! (❌)",
            color=discord.Color.red()
        )
        await ctx.send(f"{ctx.author.mention} 🎮 {opponent.mention}")  # pings before embed
        message = await ctx.send(embed=embed, view=view)
        view.message = message
        self.active_games[ctx.channel.id] = view

    @app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe with someone (slash).")
    async def tictactoe_slash(self, interaction: discord.Interaction, opponent: discord.Member):
        if interaction.channel_id in self.active_games:
            return await interaction.response.send_message("A game is already running in this channel!", ephemeral=True)

        view = TicTacToe(self, interaction, interaction.user, opponent)
        embed = discord.Embed(
            title="❌ Tic-Tac-Toe ⭕",
            description=f"{interaction.user.mention} vs {opponent.mention}\nIt’s {interaction.user.mention}'s turn! (❌)",
            color=discord.Color.red()
        )
        await interaction.response.send_message(f"{interaction.user.mention} 🎮 {opponent.mention}")
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg
        self.active_games[interaction.channel_id] = view

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.channel_id in self.active_games:
            view = self.active_games.pop(payload.channel_id)
            if view.message and view.message.id == payload.message_id:
                embed = discord.Embed(
                    title="Tic-Tac-Toe",
                    description="Game ended because the game message was deleted. 🗑️",
                    color=discord.Color.greyple()
                )
                try:
                    await view.message.edit(embed=embed, view=view.disable_all())
                except:
                    pass
                view.stop()


async def setup(bot):
    await bot.add_cog(TicTacToeCog(bot))
