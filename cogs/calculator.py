import discord
from discord.ext import commands
from discord import app_commands
import asyncio

class CalculatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="calculator")
    async def calculator(self, ctx):
        """Launch an interactive calculator."""
        view = CalculatorView(ctx.author)
        embed = discord.Embed(
            title="🖩 Calculator",
            description="```\n0\n```",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)

class CalculatorView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)  # 5 min timeout
        self.user = user
        self.expression = ""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the user who ran the command
        if interaction.user != self.user:
            await interaction.response.send_message("❌ You cannot use this calculator.", ephemeral=True)
            return False
        return True

    def update_embed(self, interaction: discord.Interaction):
        # Update embed with current expression
        if self.expression == "":
            display = "0"
        else:
            display = self.expression
        embed = discord.Embed(
            title="🖩 Calculator",
            description=f"```\n{display}\n```",
            color=discord.Color.blue()
        )
        return embed

    # Number buttons
    @discord.ui.button(label="7", style=discord.ButtonStyle.secondary)
    async def seven(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "7"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="8", style=discord.ButtonStyle.secondary)
    async def eight(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "8"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="9", style=discord.ButtonStyle.secondary)
    async def nine(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "9"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="÷", style=discord.ButtonStyle.primary)
    async def divide(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "/"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    # Row 2
    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary)
    async def four(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "4"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="5", style=discord.ButtonStyle.secondary)
    async def five(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "5"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="6", style=discord.ButtonStyle.secondary)
    async def six(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "6"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="×", style=discord.ButtonStyle.primary)
    async def multiply(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "*"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    # Row 3
    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary)
    async def one(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "1"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary)
    async def two(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "2"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary)
    async def three(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "3"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="-", style=discord.ButtonStyle.primary)
    async def minus(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "-"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    # Row 4
    @discord.ui.button(label="0", style=discord.ButtonStyle.secondary)
    async def zero(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "0"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label=".", style=discord.ButtonStyle.secondary)
    async def dot(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "."
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="=", style=discord.ButtonStyle.success)
    async def equals(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            result = eval(self.expression)
            self.expression = str(result)
        except:
            self.expression = "Error"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    @discord.ui.button(label="+", style=discord.ButtonStyle.primary)
    async def plus(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression += "+"
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)

    # Optional row: Clear
    @discord.ui.button(label="C", style=discord.ButtonStyle.danger)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.expression = ""
        await interaction.response.edit_message(embed=self.update_embed(interaction), view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(CalculatorCog(bot))