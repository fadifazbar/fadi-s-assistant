import discord
from discord.ext import commands
from discord import app_commands


class Snipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.deleted_messages = {}  # channel_id -> [messages]
        self.edited_messages = {}   # channel_id -> [{"before": before, "after": after}]

    # ---------- Listeners ----------
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        self.deleted_messages.setdefault(message.channel.id, []).append(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return
        self.edited_messages.setdefault(before.channel.id, []).append({"before": before, "after": after})

    # ---------- Helpers ----------
    def build_deleted_embed(self, message: discord.Message):
        embed = discord.Embed(
            description=message.content,
            color=discord.Color.red()
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        return embed

    def build_edited_embed(self, edit):
        before, after = edit["before"], edit["after"]
        embed = discord.Embed(
            title="Message Edited",
            color=discord.Color.orange()
        )
        embed.add_field(name="Before", value=before.content or "*no content*", inline=False)
        embed.add_field(name="After", value=after.content or "*no content*", inline=False)
        embed.set_author(name=before.author.display_name, icon_url=before.author.display_avatar.url)
        return embed

    # ---------- Prefix Commands ----------
    @commands.command(name="snipe")
    async def snipe_prefix(self, ctx):
        """Shows the last deleted message in this channel."""
        deleted = self.deleted_messages.get(ctx.channel.id, [])
        if not deleted:
            return await ctx.send("No deleted messages to snipe!")

        embed = self.build_deleted_embed(deleted[-1])
        embed.set_footer(text=f"Deleted message 1/{len(deleted)}")
        view = SnipeView(self, ctx.channel.id, mode="deleted")
        await ctx.send(embed=embed, view=view)

    @commands.command(name="editsnipe")
    async def editsnipe_prefix(self, ctx):
        """Shows the last edited message in this channel."""
        edited = self.edited_messages.get(ctx.channel.id, [])
        if not edited:
            return await ctx.send("No edited messages to snipe!")

        embed = self.build_edited_embed(edited[-1])
        embed.set_footer(text=f"Edited message 1/{len(edited)}")
        view = SnipeView(self, ctx.channel.id, mode="edited")
        await ctx.send(embed=embed, view=view)

    # ---------- Slash Commands ----------
    @app_commands.command(name="snipe", description="View the last deleted message in this channel")
    async def snipe_slash(self, interaction: discord.Interaction):
        deleted = self.deleted_messages.get(interaction.channel.id, [])
        if not deleted:
            return await interaction.response.send_message(
                "❌ No deleted messages to snipe!",
                ephemeral=True
            )

        embed = self.build_deleted_embed(deleted[-1])
        embed.set_footer(text=f"Deleted message 1/{len(deleted)}")
        view = SnipeView(self, interaction.channel.id, mode="deleted")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="editsnipe", description="View the last edited message in this channel")
    async def editsnipe_slash(self, interaction: discord.Interaction):
        edited = self.edited_messages.get(interaction.channel.id, [])
        if not edited:
            return await interaction.response.send_message(
                "❌ No edited messages to snipe!",
                ephemeral=True
            )

        embed = self.build_edited_embed(edited[-1])
        embed.set_footer(text=f"Edited message 1/{len(edited)}")
        view = SnipeView(self, interaction.channel.id, mode="edited")
        await interaction.response.send_message(embed=embed, view=view)


# ---------- Buttons ----------
class SnipeView(discord.ui.View):
    def __init__(self, ctx, snipes, edited_snipes):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.snipes = snipes
        self.edited_snipes = edited_snipes
        self.index = 0
        self.showing_deleted = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command invoker to use the buttons"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "❌ You can’t control this menu (only the command user can).", 
                ephemeral=True
            )
            return False
        return True


    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.mode == "deleted":
            messages = self.cog.deleted_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No deleted messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index - 1) % len(messages)
            embed = self.cog.build_deleted_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Deleted message {self.current_index + 1}/{len(messages)}")
        else:
            messages = self.cog.edited_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No edited messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index - 1) % len(messages)
            embed = self.cog.build_edited_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Edited message {self.current_index + 1}/{len(messages)}")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.mode == "deleted":
            messages = self.cog.deleted_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No deleted messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index + 1) % len(messages)
            embed = self.cog.build_deleted_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Deleted message {self.current_index + 1}/{len(messages)}")
        else:
            messages = self.cog.edited_messages.get(self.channel_id, [])
            if not messages:
                return await interaction.response.send_message("No edited messages to navigate!", ephemeral=True)

            self.current_index = (self.current_index + 1) % len(messages)
            embed = self.cog.build_edited_embed(messages[-(self.current_index + 1)])
            embed.set_footer(text=f"Edited message {self.current_index + 1}/{len(messages)}")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Deleted", style=discord.ButtonStyle.red)
    async def deleted_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        messages = self.cog.deleted_messages.get(self.channel_id, [])
        if messages:
            self.mode = "deleted"
            self.current_index = 0
            embed = self.cog.build_deleted_embed(messages[-1])
            embed.set_footer(text=f"Deleted message 1/{len(messages)}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=discord.Embed(
                description="No deleted messages.",
                color=discord.Color.red()
            ), view=self)

    @discord.ui.button(label="Edited", style=discord.ButtonStyle.blurple)
    async def edited_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        messages = self.cog.edited_messages.get(self.channel_id, [])
        if messages:
            self.mode = "edited"
            self.current_index = 0
            embed = self.cog.build_edited_embed(messages[-1])
            embed.set_footer(text=f"Edited message 1/{len(messages)}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=discord.Embed(
                description="No edited messages.",
                color=discord.Color.orange()
            ), view=self)


# ---------- Setup ----------
async def setup(bot):
    await bot.add_cog(Snipe(bot))
