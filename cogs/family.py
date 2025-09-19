import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import os

DATA_FILE = "/data/family.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class AcceptDeclineView(ui.View):
    def __init__(self, proposer_id, target_id, action):
        super().__init__(timeout=90)
        self.proposer_id = proposer_id
        self.target_id = target_id
        self.action = action
        self.result = None

    @ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.target_id:
            return await interaction.response.send_message("This isn’t your proposal.", ephemeral=True)
        self.result = True
        self.stop()
        await interaction.response.edit_message(content=f"{interaction.user.mention} accepted the {self.action}!", view=None)

    @ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.target_id:
            return await interaction.response.send_message("This isn’t your proposal.", ephemeral=True)
        self.result = False
        self.stop()
        await interaction.response.edit_message(content=f"{interaction.user.mention} declined the {self.action}.", view=None)

class DisownDropdown(ui.Select):
    def __init__(self, parent_id, kids):
        options = [
            discord.SelectOption(label=f"Child: {kid}", value=str(kid)) for kid in kids
        ]
        super().__init__(placeholder="Choose a child to disown", min_values=1, max_values=1, options=options)
        self.parent_id = parent_id
        self.result = None

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_id:
            return await interaction.response.send_message("This menu isn’t for you.", ephemeral=True)
        self.result = int(self.values[0])
        self.view.stop()
        await interaction.response.edit_message(content=f"You disowned <@{self.result}>.", view=None, embed=None)

class DisownView(ui.View):
    def __init__(self, parent_id, kids):
        super().__init__(timeout=60)
        self.dropdown = DisownDropdown(parent_id, kids)
        self.add_item(self.dropdown)

class Family(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()

    def save(self):
        save_data(self.data)

    def get_user(self, user_id):
        if str(user_id) not in self.data:
            self.data[str(user_id)] = {"married_to": None, "kids": [], "parent": None}
        return self.data[str(user_id)]

    @app_commands.command(name="marry", description="Propose marriage to someone")
    async def marry(self, interaction: discord.Interaction, member: discord.Member):
        proposer = self.get_user(interaction.user.id)
        target = self.get_user(member.id)

        if proposer["married_to"]:
            return await interaction.response.send_message("You are already married!", ephemeral=True)
        if target["married_to"]:
            return await interaction.response.send_message("They are already married!", ephemeral=True)

        view = AcceptDeclineView(interaction.user.id, member.id, "marriage proposal")
        await interaction.response.send_message(f"{member.mention}, {interaction.user.mention} is proposing to you!", view=view)
        await view.wait()

        if view.result:
            proposer["married_to"] = member.id
            target["married_to"] = interaction.user.id
            self.save()

    @app_commands.command(name="adopt", description="Adopt a child")
    async def adopt(self, interaction: discord.Interaction, member: discord.Member):
        parent = self.get_user(interaction.user.id)
        child = self.get_user(member.id)

        if len(parent["kids"]) >= 7:
            return await interaction.response.send_message("You already have 7 kids!", ephemeral=True)
        if child["parent"]:
            return await interaction.response.send_message("They already have a parent!", ephemeral=True)

        view = AcceptDeclineView(interaction.user.id, member.id, "adoption request")
        await interaction.response.send_message(f"{member.mention}, {interaction.user.mention} wants to adopt you!", view=view)
        await view.wait()

        if view.result:
            parent["kids"].append(member.id)
            child["parent"] = interaction.user.id
            self.save()

    @app_commands.command(name="disown", description="Disown one of your kids")
    async def disown(self, interaction: discord.Interaction):
        parent = self.get_user(interaction.user.id)
        if not parent["kids"]:
            return await interaction.response.send_message("You don’t have any kids to disown!", ephemeral=True)

        embed = discord.Embed(
            title="Choose a child to disown",
            description="Select one from the dropdown below.",
            color=discord.Color.red()
        )

        view = DisownView(interaction.user.id, parent["kids"])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.dropdown.result:
            kid_id = view.dropdown.result
            parent["kids"].remove(kid_id)
            self.get_user(kid_id)["parent"] = None
            self.save()

    @app_commands.command(name="runaway", description="Run away from your parent")
    async def runaway(self, interaction: discord.Interaction):
        child = self.get_user(interaction.user.id)
        if not child["parent"]:
            return await interaction.response.send_message("You don’t have a parent!", ephemeral=True)

        parent = self.get_user(child["parent"])
        parent["kids"].remove(interaction.user.id)
        child["parent"] = None
        self.save()
        await interaction.response.send_message("You ran away from your parent.")

    @app_commands.command(name="divorce", description="Divorce your current partner")
    async def divorce(self, interaction: discord.Interaction):
        user = self.get_user(interaction.user.id)
        if not user["married_to"]:
            return await interaction.response.send_message("You are not married!", ephemeral=True)

        partner = self.get_user(user["married_to"])
        partner["married_to"] = None
        user["married_to"] = None
        self.save()
        await interaction.response.send_message("You are now divorced.")

    @app_commands.command(name="family", description="Show your family or someone else's")
    async def family(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        user_data = self.get_user(target.id)

        partner_name = "None"
        if user_data["married_to"]:
            partner = interaction.guild.get_member(user_data["married_to"])
            partner_name = partner.display_name if partner else f"<@{user_data['married_to']}>"

        parent_name = "None"
        if user_data["parent"]:
            parent = interaction.guild.get_member(user_data["parent"])
            parent_name = parent.display_name if parent else f"<@{user_data['parent']}>"

        kids_list = "None"
        if user_data["kids"]:
            kids = []
            for kid_id in user_data["kids"]:
                kid = interaction.guild.get_member(kid_id)
                kids.append(kid.display_name if kid else f"<@{kid_id}>")
            kids_list = "\n".join(kids)

        embed = discord.Embed(
            title=f"{target.display_name}'s Family!",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Partner", value=partner_name, inline=False)
        embed.add_field(name="Parent", value=parent_name, inline=False)
        embed.add_field(name="Kids", value=kids_list, inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Family(bot))