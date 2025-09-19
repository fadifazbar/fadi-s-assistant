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
        super().__init__(timeout=120)  # wait 120s
        self.proposer_id = proposer_id
        self.target_id = target_id
        self.action = action
        self.result = None
        self.message = None  # track original message

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content=f"<@{self.target_id}> hasn’t responded to the {self.action}.", view=None)
            except:
                pass

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
        options = []
        for kid_id in kids:
            user = parent_cog.bot.get_user(int(kid_id))
            label = user.name if user else f"User {kid_id}"
            options.append(discord.SelectOption(label=label, description=f"Disown {label}"))
        super().__init__(placeholder="Choose a kid to disown", options=options)
        self.parent_cog = parent_cog
        self.parent_id = parent_id
        self.kids = kids

    async def callback(self, interaction: discord.Interaction):
        kid_name = self.values[0]
        parent_data = self.parent_cog.get_user(self.parent_id)

        kid_id = None
        for k in parent_data["kids"]:
            user = self.parent_cog.bot.get_user(int(k))
            if (user and user.name == kid_name) or str(k) == kid_name:
                kid_id = k
                break

        if kid_id is None:
            return await interaction.response.send_message("Could not find that child!", ephemeral=True)

        parent_data["kids"].remove(kid_id)
        self.parent_cog.get_user(kid_id)["parent"] = None
        self.parent_cog.save()
        await interaction.response.send_message(f"You disowned {kid_name}.")
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

    async def fetch_username(self, user_id):
        """Fetch username even if user is not in the server."""
        user = self.bot.get_user(int(user_id))
        if not user:
            try:
                user = await self.bot.fetch_user(int(user_id))
            except:
                return f"User {user_id}"
        return user.name

    # ---------- Shared logic ----------
    async def _marry(self, ctx, author, member):
        proposer = self.get_user(author.id)
        target = self.get_user(member.id)

        if proposer["married_to"]:
            return await self._send(ctx, "You are already married!")
        if target["married_to"]:
            return await self._send(ctx, "They are already married!")

        view = AcceptDeclineView(author.id, member.id, "marriage proposal")
        msg = await self._send(ctx, f"{member.mention}, {author.mention} is proposing to you!", view=view)
        view.message = msg
        await view.wait()

        if view.result:
            proposer["married_to"] = member.id
            target["married_to"] = author.id
            self.save()

    async def _adopt(self, ctx, author, member):
        parent = self.get_user(author.id)
        child = self.get_user(member.id)

        if len(parent["kids"]) >= 7:
            return await self._send(ctx, "You already have 7 kids!")
        if child["parent"]:
            return await self._send(ctx, "They already have a parent!")
        if parent["married_to"] == member.id or child["married_to"] == author.id:
            return await self._send(ctx, "❌ You cannot adopt your spouse!")

        view = AcceptDeclineView(author.id, member.id, "adoption request")
        msg = await self._send(ctx, f"{member.mention}, {author.mention} wants to adopt you!", view=view)
        view.message = msg
        await view.wait()

        if view.result:
            parent["kids"].append(member.id)
            child["parent"] = author.id
            self.save()

    async def _disown(self, ctx, author):
        parent = self.get_user(author.id)
        if not parent["kids"]:
            return await self._send(ctx, "You don’t have any kids!")

        view = DisownView(self, author.id, parent["kids"])
        embed = discord.Embed(title="Disown a Child", description="Choose a kid to disown", color=discord.Color.red())
        await self._send(ctx, embed=embed, view=view)

    async def _runaway(self, ctx, author):
        child = self.get_user(author.id)
        if not child["parent"]:
            return await self._send(ctx, "You don’t have a parent!")

        parent = self.get_user(child["parent"])
        parent["kids"].remove(author.id)
        child["parent"] = None
        self.save()
        return await self._send(ctx, "You ran away from your parent.")

    async def _divorce(self, ctx, author):
        person = self.get_user(author.id)
        if not person["married_to"]:
            return await self._send(ctx, "You are not married!")

        partner = self.get_user(person["married_to"])
        partner["married_to"] = None
        person["married_to"] = None
        self.save()
        return await self._send(ctx, "You are now divorced.")

    async def _family(self, ctx, author, member=None):
        user = member or author
        data = self.get_user(user.id)

        partner = await self.fetch_username(data["married_to"]) if data["married_to"] else "None"
        parent = await self.fetch_username(data["parent"]) if data["parent"] else "None"
        kids = "\n".join([await self.fetch_username(kid) for kid in data["kids"]]) if data["kids"] else "None"

        embed = discord.Embed(title=f"{user.display_name}'s Family!", color=discord.Color.blurple())
        embed.add_field(name="Partner", value=partner, inline=False)
        embed.add_field(name="Parent", value=parent, inline=False)
        embed.add_field(name="Kids", value=kids, inline=False)

        await self._send(ctx, embed=embed)

    async def _send(self, ctx, content=None, *, embed=None, view=None, ephemeral=False):
        """Helper: works for both Context and Interaction"""
        if isinstance(ctx, commands.Context):
            return await ctx.send(content, embed=embed, view=view)
        else:
            if ctx.response.is_done():
                return await ctx.followup.send(content, embed=embed, view=view, ephemeral=ephemeral)
            else:
                return await ctx.response.send_message(content, embed=embed, view=view, ephemeral=ephemeral)

    # ---------- Slash Commands ----------
    @app_commands.command(name="marry")
    @app_commands.checks.cooldown(1, 5)
    async def marry_slash(self, interaction: discord.Interaction, member: discord.User):
        await self._marry(interaction, interaction.user, member)

    @app_commands.command(name="adopt")
    @app_commands.checks.cooldown(1, 5)
    async def adopt_slash(self, interaction: discord.Interaction, member: discord.User):
        await self._adopt(interaction, interaction.user, member)

    @app_commands.command(name="disown")
    @app_commands.checks.cooldown(1, 5)
    async def disown_slash(self, interaction: discord.Interaction):
        await self._disown(interaction, interaction.user)

    @app_commands.command(name="runaway")
    @app_commands.checks.cooldown(1, 5)
    async def runaway_slash(self, interaction: discord.Interaction):
        await self._runaway(interaction, interaction.user)

    @app_commands.command(name="divorce")
    @app_commands.checks.cooldown(1, 5)
    async def divorce_slash(self, interaction: discord.Interaction):
        await self._divorce(interaction, interaction.user)

    @app_commands.command(name="family")
    @app_commands.checks.cooldown(1, 5)
    async def family_slash(self, interaction: discord.Interaction, member: discord.User = None):
        await self._family(interaction, interaction.user, member)

    # ---------- Prefix Commands ----------
    @commands.command(name="marry")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def marry_prefix(self, ctx, member: discord.User):
        await self._marry(ctx, ctx.author, member)

    @commands.command(name="adopt")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def adopt_prefix(self, ctx, member: discord.User):
        await self._adopt(ctx, ctx.author, member)

    @commands.command(name="disown")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def disown_prefix(self, ctx):
        await self._disown(ctx, ctx.author)

    @commands.command(name="runaway")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def runaway_prefix(self, ctx):
        await self._runaway(ctx, ctx.author)

    @commands.command(name="divorce")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def divorce_prefix(self, ctx):
        await self._divorce(ctx, ctx.author)

    @commands.command(name="family")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def family_prefix(self, ctx, member: discord.User = None):
        await self._family(ctx, ctx.author, member)

    # ---------- Error handler for cooldown ----------
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ Wait {int(error.retry_after)} more seconds to run that command again.", ephemeral=True)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Wait {int(error.retry_after)} more seconds to run that command again.")

async def setup(bot):
    await bot.add_cog(Family(bot))