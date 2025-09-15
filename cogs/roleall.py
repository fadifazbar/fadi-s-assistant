import asyncio
import discord
import time
from discord.ext import commands

class RoleAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="roleall")
    @commands.has_permissions(manage_roles=True)
    async def roleall(self, ctx, action: str, role: discord.Role):
        """
        Give or remove a role from all server members.
        Usage: $roleall give @role OR $roleall remove @role
        """
        if action.lower() not in ["give", "remove"]:
            return await ctx.send("❌ Invalid action! Use `give` or `remove`.")

        members = ctx.guild.members
        total = len(members)
        done = 0
        batch = []
        batch_size = 5   # members per batch
        pause_time = 2   # seconds pause between batches
        start_time = time.time()
        batch_counter = 0

        # Start embed
        embed = discord.Embed(
            title="🔄 Processing RoleAll",
            description=(
                f"{'Giving' if action.lower() == 'give' else 'Removing'} {role.mention} "
                f"for **{total} members**...\n\n"
                "⚠️ On large servers, this may take some time due to Discord rate limits."
            ),
            color=discord.Color.yellow()
        )
        msg = await ctx.send(embed=embed)

        for member in members:
            try:
                if action.lower() == "give":
                    batch.append(member.add_roles(role, reason="RoleAll command"))
                else:
                    batch.append(member.remove_roles(role, reason="RoleAll command"))
            except Exception:
                pass

            done += 1

            if len(batch) >= batch_size:
                await asyncio.gather(*batch, return_exceptions=True)
                batch.clear()
                batch_counter += 1

                # Update ETA every 5 batches
                if batch_counter % 5 == 0:
                    elapsed = time.time() - start_time
                    avg_per_member = elapsed / done if done > 0 else 0
                    remaining = (total - done) * avg_per_member
                    eta = time.strftime("%M:%S", time.gmtime(remaining))

                    progress_embed = discord.Embed(
                        title="🔄 Processing RoleAll",
                        description=(
                            f"{'Giving' if action.lower() == 'give' else 'Removing'} {role.mention}\n\n"
                            f"**Progress:** {done}/{total} members done ✅\n"
                            f"⏳ Estimated time left: ~{eta}"
                        ),
                        color=discord.Color.orange()
                    )
                    await msg.edit(embed=progress_embed)

                await asyncio.sleep(pause_time)

        if batch:
            await asyncio.gather(*batch, return_exceptions=True)

        # Final embed
        final_embed = discord.Embed(
            title="✅ RoleAll Completed",
            description=(
                f"{'Gave' if action.lower() == 'give' else 'Removed'} {role.mention} "
                f"for **{done}/{total} members**!\n\n"
                f"⏱️ Total time: {time.strftime('%M:%S', time.gmtime(time.time() - start_time))}"
            ),
            color=discord.Color.green()
        )
        await msg.edit(embed=final_embed)


async def setup(bot):
    await bot.add_cog(RoleAll(bot))