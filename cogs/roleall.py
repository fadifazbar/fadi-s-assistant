import discord
from discord.ext import commands
from discord import app_commands
import asyncio


class RoleAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Check if roles changed at all
        if before.roles == after.roles:
            return

        before_ids = {r.id for r in before.roles}
        after_ids = {r.id for r in after.roles}

        added_ids = after_ids - before_ids
        removed_ids = before_ids - after_ids

        print(f"[DEBUG] Role change detected for {after} ({after.id})")
        print(f"[DEBUG] Added: {added_ids}, Removed: {removed_ids}")

        CONTENT_CREATOR_ROLE_ID = 1363562800819077476

        # Role added → send welcome DM
        if CONTENT_CREATOR_ROLE_ID in added_ids:
            try:
                await after.send(
                    f"👋 Hi {after.mention}!\n\n"
                    "You have officially been added to **Noobs Vs Bacons's Content Creator** program. "
                    "Please follow the content creator rules (<#1363562801293033614>)."
                )
                print("[DEBUG] Sent DM for role ADD")
            except Exception as e:
                print(f"[DEBUG] Failed to DM on role add: {e}")

        # Role removed → send removal DM with embed
        if CONTENT_CREATOR_ROLE_ID in removed_ids:
            try:
                embed = discord.Embed(
                    description=(
                        f"👋 Hi {after.mention}!\n"
                        "You've been removed from the **Content Creator Program** in **Noobs Vs Bacons** "
                        "because you do not meet the **Official Requirements**. Try applying again later by "
                        "DMing the **Owner (<@1167531276467708055>)**, the **Game Manager (<@1281960117633286144>)**, "
                        "or the **Co-Owner (<@1123292111404531783>)** on Discord, but remember to read the "
                        "**Requirements (<#1364715466316189776>)**.\n\nGood Luck!"
                    ),
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url="https://i.ibb.co/QjdGBtNg")
                await after.send(embed=embed)
                print("[DEBUG] Sent DM for role REMOVE")
            except Exception as e:
                print(f"[DEBUG] Failed to DM on role remove: {e}")

    # ---------------- Shared Logic ----------------
    async def _roleall(self, ctx_or_interaction, action: str, role: discord.Role, is_slash: bool = False):
        guild = ctx_or_interaction.guild
        author = ctx_or_interaction.user if is_slash else ctx_or_interaction.author

        # Determine members to process
        if action.lower() == "give":
            members = [m for m in guild.members if role not in m.roles]
        elif action.lower() == "remove":
            members = [m for m in guild.members if role in m.roles]
        else:
            msg = "❌ Invalid action. Use `give` or `remove`."
            if is_slash:
                return await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            return await ctx_or_interaction.send(msg)

        if not members:
            msg = f"⚠️ No members to {action} the role {role.mention}."
            if is_slash:
                return await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            return await ctx_or_interaction.send(msg)

        total = len(members)
        changed = 0

        # Initial embed
        embed = discord.Embed(
            title=f"⏳ {action.capitalize()}ing Role",
            description=f"Processing {role.mention} for {total} members...\n(0/{total})",
            color=discord.Color.yellow()
        )
        embed.set_footer(text=f"Requested by {author}", icon_url=author.display_avatar.url)

        if is_slash:
            await ctx_or_interaction.response.send_message(embed=embed)
            progress_msg = await ctx_or_interaction.original_response()
        else:
            progress_msg = await ctx_or_interaction.send(embed=embed)

        # ---------------- Processing in concurrent batches ----------------
        batch_size = 25
        pause_time = 1  # seconds

        for i in range(0, len(members), batch_size):
            batch = members[i:i+batch_size]

            tasks = []
            for member in batch:
                if action.lower() == "give":
                    tasks.append(member.add_roles(role, reason=f"Mass role give by {author}"))
                else:
                    tasks.append(member.remove_roles(role, reason=f"Mass role remove by {author}"))

            # Run all role operations concurrently
            await asyncio.gather(*tasks, return_exceptions=True)

            # Update progress
            changed += len(batch)
            embed.description = f"{action.capitalize()}ing {role.mention}...\n({changed}/{total})"
            await progress_msg.edit(embed=embed)

            # Pause after each batch
            await asyncio.sleep(pause_time)

        # Final embed
        embed.title = f"✅ Finished {action.capitalize()}ing Role"
        embed.description = f"{action.capitalize()}ed {role.mention} for {changed}/{total} members."
        embed.color = discord.Color.green()
        await progress_msg.edit(embed=embed)

    # ---------------- Prefix Command ----------------
    @commands.command(name="roleall")
    @commands.has_permissions(manage_roles=True)
    async def roleall_prefix(self, ctx, action: str, role: discord.Role):
        """Mass give/remove a role (prefix)."""
        await self._roleall(ctx, action, role, is_slash=False)

    # ---------------- Slash Command ----------------
    @app_commands.command(
        name="roleall",
        description="Mass give/remove a role"
    )
    @app_commands.describe(
        action="Choose 'give' to assign or 'remove' to take away the role.",
        role="The role to give or remove."
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roleall_slash(self, interaction: discord.Interaction, action: str, role: discord.Role):
        """Mass give/remove a role (slash)."""
        await self._roleall(interaction, action, role, is_slash=True)


async def setup(bot):
    await bot.add_cog(RoleAll(bot))