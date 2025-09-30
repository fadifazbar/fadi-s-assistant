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
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


class CalculatorView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)  # 5 min timeout
        self.user = user
        self.expression = ""
        self.last_result = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("❌ You cannot use this calculator.", ephemeral=True)
            return False
        return True

    def update_embed(self):
        if self.last_result is not None:
            display = f"{self.expression}\nResult: {self.last_result}"
        else:
            display = self.expression if self.expression else "0"

        embed = discord.Embed(
            title="🧮 Calculator",
            description=f"```\n{display}\n```",
            color=discord.Color.blue()
        )
        return embed

    # ------------------- Row 0 -------------------
    @discord.ui.button(label="1️⃣", style=discord.ButtonStyle.blurple, row=0)
    async def one(self, interaction, button):
        self.expression += "1"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="2️⃣", style=discord.ButtonStyle.blurple, row=0)
    async def two(self, interaction, button):
        self.expression += "2"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="3️⃣", style=discord.ButtonStyle.blurple, row=0)
    async def three(self, interaction, button):
        self.expression += "3"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="➕", style=discord.ButtonStyle.success, row=0)
    async def plus(self, interaction, button):
        self.expression += "+"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # ------------------- Row 1 -------------------
    @discord.ui.button(label="4️⃣", style=discord.ButtonStyle.blurple, row=1)
    async def four(self, interaction, button):
        self.expression += "4"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="5️⃣", style=discord.ButtonStyle.blurple, row=1)
    async def five(self, interaction, button):
        self.expression += "5"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="6️⃣", style=discord.ButtonStyle.blurple, row=1)
    async def six(self, interaction, button):
        self.expression += "6"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="➖", style=discord.ButtonStyle.success, row=1)
    async def minus(self, interaction, button):
        self.expression += "-"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # ------------------- Row 2 -------------------
    @discord.ui.button(label="7️⃣", style=discord.ButtonStyle.blurple, row=2)
    async def seven(self, interaction, button):
        self.expression += "7"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="8️⃣", style=discord.ButtonStyle.blurple, row=2)
    async def eight(self, interaction, button):
        self.expression += "8"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="9️⃣", style=discord.ButtonStyle.blurple, row=2)
    async def nine(self, interaction, button):
        self.expression += "9"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="✖️", style=discord.ButtonStyle.success, row=2)
    async def multiply(self, interaction, button):
        self.expression += "*"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # ------------------- Row 3 -------------------
    @discord.ui.button(label="🔘", style=discord.ButtonStyle.success, row=3)
    async def dot(self, interaction, button):
        self.expression += "."
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="0️⃣", style=discord.ButtonStyle.blurple, row=3)
    async def zero(self, interaction, button):
        self.expression += "0"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="➗", style=discord.ButtonStyle.success, row=3)
    async def divide(self, interaction, button):
        self.expression += "/"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    # ------------------- Row 4 -------------------
    @discord.ui.button(label="©️", style=discord.ButtonStyle.danger, row=4)
    async def clear(self, interaction, button):
        self.expression = ""
        self.last_result = None
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="⌫", style=discord.ButtonStyle.danger, row=4)
    async def backspace(self, interaction, button):
        self.expression = self.expression[:-1]
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="🟰", style=discord.ButtonStyle.success, row=4)
    async def equals(self, interaction, button):
        try:
            self.last_result = eval(self.expression)
        except:
            self.last_result = "Error"
        await interaction.response.edit_message(embed=self.update_embed(), view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(CalculatorCog(bot))