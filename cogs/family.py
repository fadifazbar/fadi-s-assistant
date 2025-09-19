import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
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
    def __init__(self, parent_cog, parent_id, kids):
        options = [discord.SelectOption(label=str(kid), description=f"Disown {kid}") for kid in kids]
        super().__init__(placeholder="Choose a kid to disown", options=options)
        self.parent_cog = parent_cog
        self.parent_id = parent_id
        self.kids = kids

    async def callback(self, interaction: discord.Interaction):
        kid_name = self.values[0]
        parent_data = self.parent_cog.get_user(self.parent_id)

        kid_id = None
        for k in parent_data["kids"]:
            if str(k) == kid_name:
                kid_id = k
                break

        if kid_id is None:
            return await interaction.response.send_message("Could not find that child!", ephemeral=True)

        parent_data["kids"].remove(kid_id)
        self.parent_cog.get_user(kid_id)["parent"] = None
        self.parent_cog.save()
        await interaction.response.send_message(f"You disowned <@{kid_id}>.")
        self.view.stop()

class DisownView(ui.View):
    def __init__(self, parent_cog, parent_id, kids):
        super().__init__()
        self.add_item(DisownDropdown(parent_cog, parent_id, kids))

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

    # ---------- Shared logic ----------
    async def _marry(self, ctx, author, member):
        proposer = self.get_user(author.id)
        target = self.get_user(member.id)

        if proposer["married_to"]:
            return await ctx.send("You are already married!") if isinstance(ctx, commands.Context) else await ctx.response.send_message("You are already married!", ephemeral=True)
        if target["married_to"]:
            return await ctx.send("They are already married!") if isinstance(ctx, commands.Context) else await ctx.response.send_message("They are already married!", ephemeral=True)

        view = AcceptDeclineView(author.id, member.id, "marriage proposal")

        if isinstance(ctx, commands.Context):
            msg = await ctx.send(f"{member.mention}, {author.mention} is proposing to you!", view=view)
        else:
            await ctx.response.send_message(f"{member.mention}, {author.mention} is proposing to you!", view=view)

        await view.wait()

        if view.result:
            proposer["married_to"] = member.id
            target["married_to"] = author.id
            self.save()

    async def _adopt(self, ctx, author, member):
        parent = self.get_user(author.id)
        child = self.get_user(member.id)

        if len(parent["kids"]) >= 7:
            return await ctx.send("You already have 7 kids!") if isinstance(ctx, commands.Context) else await ctx.response.send_message("You already have 7 kids!", ephemeral=True)
        if child["parent"]:
            return await ctx.send("They already have a parent!") if isinstance(ctx, commands.Context) else await ctx.response.send_message("They already have a parent!", ephemeral=True)

        view = AcceptDeclineView(author.id, member.id, "adoption request")

        if isinstance(ctx, commands.Context):
            msg = await ctx.send(f"{member.mention}, {author.mention} wants to adopt you!", view=view)
        else:
            await ctx.response.send_message(f"{member.mention}, {author.mention} wants to adopt you!", view=view)

        await view.wait()

        if view.result:
            parent["kids"].append(member.id)
            child["parent"] = author.id
            self.save()

    async def _disown(self, ctx, author):
        parent = self.get_user(author.id)
        if not parent["kids"]:
            return await ctx.send("You don’t have any kids!") if isinstance(ctx, commands.Context) else await ctx.response.send_message("You don’t have any kids!", ephemeral=True)

        view = DisownView(self, author.id, parent["kids"])

        if isinstance(ctx, commands.Context):
            await ctx.send("Choose a kid to disown:", view=view)
        else:
            embed = discord.Embed(title="Disown a Child", description="Choose a kid to disown", color=discord.Color.red())
            await ctx.response.send_message(embed=embed, view=view)

    async def _runaway(self, ctx, author):
        child = self.get_user(author.id)
        if not child["parent"]:
            return await ctx.send("You don’t have a parent!") if isinstance(ctx, commands.Context) else await ctx.response.send_message("You don’t have a parent!", ephemeral=True)

        parent = self.get_user(child["parent"])
        parent["kids"].remove(author.id)
        child["parent"] = None
        self.save()
        return await ctx.send("You ran away from your parent.") if isinstance(ctx, commands.Context) else await ctx.response.send_message("You ran away from your parent.")

    async def _divorce(self, ctx, author):
        person = self.get_user(author.id)
        if not person["married_to"]:
            return await ctx.send("You are not married!") if isinstance(ctx, commands.Context) else await ctx.response.send_message("You are not married!", ephemeral=True)

        partner = self.get_user(person["married_to"])
        partner["married_to"] = None
        person["married_to"] = None
        self.save()
        return await ctx.send("You are now divorced.") if isinstance(ctx, commands.Context) else await ctx.response.send_message("You are now divorced.")

    async def _family(self, ctx, author, member=None):
        user = member or author
        data = self.get_user(user.id)

        partner = f"<@{data['married_to']}>" if data["married_to"] else "None"
        parent = f"<@{data['parent']}>" if data["parent"] else "None"
        kids = "\n".join([f"<@{kid}>" for kid in data["kids"]]) if data["kids"] else "None"

        embed = discord.Embed(title=f"{user.display_name}'s Family!", color=discord.Color.blurple())
        embed.add_field(name="Partner", value=partner, inline=False)
        embed.add_field(name="Parent", value=parent, inline=False)
        embed.add_field(name="Kids", value=kids, inline=False)

        return await ctx.send(embed=embed) if isinstance(ctx, commands.Context) else await ctx.response.send_message(embed=embed)

    # ---------- Slash Commands ----------
    @app_commands.command(name="marry")
    async def marry_slash(self, interaction: discord.Interaction, member: discord.Member):
        await self._marry(interaction, interaction.user, member)

    @app_commands.command(name="adopt")
    async def adopt_slash(self, interaction: discord.Interaction, member: discord.Member):
        await self._adopt(interaction, interaction.user, member)

    @app_commands.command(name="disown")
    async def disown_slash(self, interaction: discord.Interaction):
        await self._disown(interaction, interaction.user)

    @app_commands.command(name="runaway")
    async def runaway_slash(self, interaction: discord.Interaction):
        await self._runaway(interaction, interaction.user)

    @app_commands.command(name="divorce")
    async def divorce_slash(self, interaction: discord.Interaction):
        await self._divorce(interaction, interaction.user)

    @app_commands.command(name="family")
    async def family_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await self._family(interaction, interaction.user, member)

    # ---------- Prefix Commands ----------
    @commands.command(name="marry")
    async def marry_prefix(self, ctx, member: discord.Member):
        await self._marry(ctx, ctx.author, member)

    @commands.command(name="adopt")
    async def adopt_prefix(self, ctx, member: discord.Member):
        await self._adopt(ctx, ctx.author, member)

    @commands.command(name="disown")
    async def disown_prefix(self, ctx):
        await self._disown(ctx, ctx.author)

    @commands.command(name="runaway")
    async def runaway_prefix(self, ctx):
        await self._runaway(ctx, ctx.author)

    @commands.command(name="divorce")
    async def divorce_prefix(self, ctx):
        await self._divorce(ctx, ctx.author)

    @commands.command(name="family")
    async def family_prefix(self, ctx, member: discord.Member = None):
        await self._family(ctx, ctx.author, member)

async def setup(bot):
    await bot.add_cog(Family(bot))