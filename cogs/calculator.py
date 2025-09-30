import discord
from discord.ext import commands
from discord import app_commands

class CalculatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Prefix command
    @commands.command(name="calculator", aliases=["calc"])
    async def calculator_prefix(self, ctx):
        """Launch an interactive calculator (prefix)."""
        view = CalculatorView(ctx.author)
        embed = discord.Embed(
            title="🖩 Calculator",
            description="```\n0\n```",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)

    # Slash command
    @app_commands.command(name="calculator", description="Launch an interactive calculator")
    async def calculator_slash(self, interaction: discord.Interaction):
        """Launch an interactive calculator (slash)."""
        view = CalculatorView(interaction.user)
        embed = discord.Embed(
            title="🖩 Calculator",
            description="```\n0\n```",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


class CalculatorView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)  # 5 min timeout
        self.user = user
        self.expression = ""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("❌ You cannot use this calculator.", ephemeral=True)
            return False
        return True

    def update_embed(self):
        display = self.expression if self.expression else "0"
        embed = discord.Embed(
            title="🖩 Calculator",
            description=f"```\n{display}\n```",
            color=discord.Color.blue()
        )
        return embed

    # Row 1
    @discord.ui.button(label="1", style=discord.ButtonStyle.blurple)
    async def one(self, interaction, button):
        self.expression += "1"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def two(self, interaction, button):
        self.expression += "2"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="3", style=discord.ButtonStyle.blurple)
    async def three(self, interaction, button):
        self.expression += "3"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="+", style=discord.ButtonStyle.success)
    async def plus(self, interaction, button):
        self.expression += "+"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # Row 2
    @discord.ui.button(label="4", style=discord.ButtonStyle.blurple)
    async def four(self, interaction, button):
        self.expression += "4"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="5", style=discord.ButtonStyle.blurple)
    async def five(self, interaction, button):
        self.expression += "5"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="6", style=discord.ButtonStyle.blurple)
    async def six(self, interaction, button):
        self.expression += "6"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="-", style=discord.ButtonStyle.success)
    async def minus(self, interaction, button):
        self.expression += "-"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # Row 3
    @discord.ui.button(label="7", style=discord.ButtonStyle.blurple)
    async def seven(self, interaction, button):
        self.expression += "7"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="8", style=discord.ButtonStyle.blurple)
    async def eight(self, interaction, button):
        self.expression += "8"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="9", style=discord.ButtonStyle.blurple)
    async def nine(self, interaction, button):
        self.expression += "9"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="×", style=discord.ButtonStyle.success)
    async def multiply(self, interaction, button):
        self.expression += "*"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # Row 4
    @discord.ui.button(label=".", style=discord.ButtonStyle.success)
    async def dot(self, interaction, button):
        self.expression += "."
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="0", style=discord.ButtonStyle.blurple)
    async def zero(self, interaction, button):
        self.expression += "0"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="÷", style=discord.ButtonStyle.success)
    async def divide(self, interaction, button):
        self.expression += "/"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # Row 5
    @discord.ui.button(label="C", style=discord.ButtonStyle.danger)
    async def clear(self, interaction, button):
        self.expression = ""
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="⌫", style=discord.ButtonStyle.danger)
    async def backspace(self, interaction, button):
        self.expression = self.expression[:-1]
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="=", style=discord.ButtonStyle.success)
    async def equals(self, interaction, button):
        try:
            self.expression = str(eval(self.expression))
        except:
            self.expression = "Error"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(CalculatorCog(bot))