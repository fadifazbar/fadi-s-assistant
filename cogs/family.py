import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import json
import os

Embed_Colors = {
    "red": discord.Color(0xFF0000),
    "orange": discord.Color(0xFF6A00),
    "yellow": discord.Color(0xFFEA00),
    "green": discord.Color(0x2FFF00),
    "darkgreen": discord.Color(0x126300),
    "cyan": discord.Color(0x00F2FF),
    "blue": discord.Color(0x009DFF),
    "darkblue": discord.Color(0x1100FF),
    "purple": discord.Color(0x9900FF),
    "pink": discord.Color(0xFF00A6)
}

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
            return await interaction.response.send_message("❌ This isn’t your proposal.", ephemeral=True)
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
            return await interaction.response.send_message("❌ Could not find that child!", ephemeral=True)

        parent_data["kids"].remove(kid_id)
        self.parent_cog.get_user(kid_id)["parent"] = None
        self.parent_cog.save()
        await interaction.response.send_message(f"😭 You disowned {kid_name}.")
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

    def is_whitelisted(self, user_id: int):
        # ✅ You can set unique allowed IDs per command if you want
        allowed_ids = {1127551581957664829, 1167531276467708055, 1115297901829181440, 1123292111404531783, 1139306059358539796, 1369169749946400798}  # replace with your IDs
        return user_id in allowed_ids

    async def force_check(self, ctx_or_inter):
        user_id = ctx_or_inter.user.id if isinstance(ctx_or_inter, discord.Interaction) else ctx_or_inter.author.id
        if not self.is_whitelisted(user_id):
            if isinstance(ctx_or_inter, discord.Interaction):
                await ctx_or_inter.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
            else:
                await ctx_or_inter.send("❌ You are not allowed to use this command.", ephemeral=True)
            return False
        return True

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
    if author.id == member.id:  # Prevent self-marriage
        return await self._send(ctx, "❌ You cannot marry yourself!")

    proposer = self.get_user(author.id)
    target = self.get_user(member.id)

    if proposer["married_to"]:
        return await self._send(ctx, "💍 You are already married!")
    if target["married_to"]:
        return await self._send(ctx, "💍 They are already married!")

    view = AcceptDeclineView(author.id, member.id, "marriage proposal")
    msg = await self._send(ctx, f"💍 {member.mention}, {author.mention} is proposing to you!", view=view)
    view.message = msg
    await view.wait()

    if view.result:
        proposer["married_to"] = member.id
        target["married_to"] = author.id
        self.save()


async def _adopt(self, ctx, author, member):
    if author.id == member.id:  # Prevent self-adoption
        return await self._send(ctx, "❌ You cannot adopt yourself!")

    parent = self.get_user(author.id)
    child = self.get_user(member.id)

    if len(parent["kids"]) >= 7:
        return await self._send(ctx, "👼 You already have 7 kids!")
    if child["parent"]:
        return await self._send(ctx, "👨 They already have a parent!")
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
            return await self._send(ctx, "❌ You don’t have any kids!")

        view = DisownView(self, author.id, parent["kids"])
        embed = discord.Embed(title="😭 Disown a Child", description="Choose a kid to disown", color=Embed_Colors["red"])
        await self._send(ctx, embed=embed, view=view)

    async def _runaway(self, ctx, author):
        child = self.get_user(author.id)
        if not child["parent"]:
            return await self._send(ctx, "You don’t have a parent!")

        parent = self.get_user(child["parent"])
        parent["kids"].remove(author.id)
        child["parent"] = None
        self.save()
        return await self._send(ctx, "😭 You ran away from your parent.")

    async def _divorce(self, ctx, author):
        person = self.get_user(author.id)
        if not person["married_to"]:
            return await self._send(ctx, "❌ You are not married!")

        partner = self.get_user(person["married_to"])
        partner["married_to"] = None
        person["married_to"] = None
        self.save()
        return await self._send(ctx, "😭 You are now divorced.")

    async def _family(self, ctx, author, member=None):
        user = member or author
        data = self.get_user(user.id)

        # Direct relationships
        partner = await self.fetch_username(data["married_to"]) if data["married_to"] else "None"
        parent = await self.fetch_username(data["parent"]) if data["parent"] else "None"
        kids = "\n".join([await self.fetch_username(kid) for kid in data["kids"]]) if data["kids"] else "None"

        # --- Other Parent ---
        other_parent_id = None
        other_parent = "None"
        if data["parent"]:
            parent_data = self.get_user(data["parent"])
            if parent_data["married_to"]:
                other_parent_id = parent_data["married_to"]
                other_parent = await self.fetch_username(other_parent_id)

        # --- Grandparents ---
        grandparents = set()

        async def add_both_parents(child_id):
            if child_id:
                child_data = self.get_user(child_id)
                if child_data["parent"]:
                    gp1 = await self.fetch_username(child_data["parent"])
                    grandparents.add(gp1)
                if child_data["parent"]:
                    parent_data = self.get_user(child_data["parent"])
                    if parent_data["married_to"]:
                        gp2 = await self.fetch_username(parent_data["married_to"])
                        grandparents.add(gp2)

        if data["parent"]:
            await add_both_parents(data["parent"])
        if other_parent_id:
            await add_both_parents(other_parent_id)

        grandparents_text = "\n".join(grandparents) if grandparents else "None"

        # --- Brothers / Siblings ---
        siblings_set = set()

        async def add_siblings(parent_id):
            if parent_id:
                parent_data = self.get_user(parent_id)
                for kid in parent_data["kids"]:
                    if kid != user.id:
                        siblings_set.add(await self.fetch_username(kid))

        if data["parent"]:
            await add_siblings(data["parent"])
        if other_parent_id:
            await add_siblings(other_parent_id)

        siblings = "\n".join(siblings_set) if siblings_set else "None"

        # Build embed
        embed = discord.Embed(
            title=f"{user.display_name}'s Family!",
            color=Embed_Colors["yellow"]
        )
        embed.add_field(name="👴 Grandparents", value=grandparents_text, inline=False)
        embed.add_field(name="💍 Partner", value=partner, inline=False)
        embed.add_field(name="👨 Parent", value=parent, inline=False)
        embed.add_field(name="👩 Other Parent", value=other_parent, inline=False)
        embed.add_field(name="👼 Kids", value=kids, inline=False)
        embed.add_field(name="👦 Siblings", value=siblings, inline=False)

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


    # ================= Force Marry =================
    @app_commands.command(name="forcemarry", description="Forcefully marry two people (only whitelisted users).")
    async def forcemarry_slash(self, interaction: discord.Interaction, user1: discord.User, user2: discord.User):
        if not await self.force_check(interaction):
            return
        await self._forcemarry(interaction, user1, user2)

    @commands.command(name="forcemarry", aliases=["fm"])
    async def forcemarry_prefix(self, ctx: commands.Context, user1: discord.User, user2: discord.User = None):
        if not await self.force_check(ctx):
            return

        # if only one mention → marry the caller with that mention
        if user2 is None:
            user2 = user1
            user1 = ctx.author

        await self._forcemarry(ctx, user1, user2)

    async def _forcemarry(self, ctx_or_inter, user1: discord.User, user2: discord.User):
        u1 = self.get_user(user1.id)
        u2 = self.get_user(user2.id)

        if u1["married_to"] or u2["married_to"]:
            msg = "❌ One of them is already married."
        else:
            u1["married_to"] = user2.id
            u2["married_to"] = user1.id
            self.save()
            msg = f"💍 {user1.name} has been forcefully married to {user2.name}."

        if isinstance(ctx_or_inter, discord.Interaction):
            await ctx_or_inter.response.send_message(msg)
        else:
            await ctx_or_inter.send(msg)

    # ================= Force Adopt =================
    @app_commands.command(name="forceadopt", description="Forcefully adopt a kid (only whitelisted users).")
    async def forceadopt_slash(self, interaction: discord.Interaction, parent: discord.User, child: discord.User):
        if not await self.force_check(interaction):
            return
        await self._forceadopt(interaction, parent, child)

    @commands.command(name="forceadopt", aliases=["fa"])
    async def forceadopt_prefix(self, ctx: commands.Context, parent: discord.User, child: discord.User = None):
        if not await self.force_check(ctx):
            return

        # if only one mention → the caller is parent, mention is child
        if child is None:
            child = parent
            parent = ctx.author

        await self._forceadopt(ctx, parent, child)

    async def _forceadopt(self, ctx_or_inter, parent: discord.User, child: discord.User):
        parent_data = self.get_user(parent.id)
        child_data = self.get_user(child.id)

        if child_data["parent"]:
            msg = "❌ That kid already has a parent."
        elif parent_data["married_to"] == child.id:
            msg = "❌ You cannot adopt your partner."
        else:
            parent_data["kids"].append(child.id)
            child_data["parent"] = parent.id
            self.save()
            msg = f"👶 {child.name} has been forcefully adopted by {parent.name}."

        if isinstance(ctx_or_inter, discord.Interaction):
            await ctx_or_inter.response.send_message(msg)
        else:
            await ctx_or_inter.send(msg)

    # ================= Force Divorce =================
    @app_commands.command(name="forcedivorce", description="Forcefully divorce a user and their partner (only whitelisted users).")
    async def forcedivorce_slash(self, interaction: discord.Interaction, user: discord.User):
        if not await self.force_check(interaction):
            return
        await self._forcedivorce(interaction, user)

    @commands.command(name="forcedivorce", aliases=["fd"])
    async def forcedivorce_prefix(self, ctx: commands.Context, user: discord.User):
        if not await self.force_check(ctx):
            return
        await self._forcedivorce(ctx, user)

    async def _forcedivorce(self, ctx_or_inter, user: discord.User):
        u = self.get_user(user.id)

        # Check if the user is even married
        if not u["married_to"]:
            msg = f"❌ {user.name} is not married to anyone."
        else:
            partner_id = u["married_to"]
            partner_user = self.get_user(partner_id)

            # Break both sides
            u["married_to"] = None
            partner_user["married_to"] = None
            self.save()

            partner_name = (await self.bot.fetch_user(partner_id)).name
            msg = f"💔 {user.name} and {partner_name} have been forcefully divorced."

        # Send message in the correct context
        if isinstance(ctx_or_inter, discord.Interaction):
            await ctx_or_inter.response.send_message(msg)
        else:
            await ctx_or_inter.send(msg)





    
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
