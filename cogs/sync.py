# cogs/sync.py
import discord
from discord.ext import commands

class SyncCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sync", help="Sync slash commands. Usage: !sync [here|all]")
    @commands.is_owner()
    async def sync_prefix(self, ctx, scope: str = None):
        try:
            if scope == "here":
                synced = await self.bot.tree.sync(guild=ctx.guild)
                msg = f"✅ Synced **{len(synced)}** commands to **{ctx.guild.name}**."
            elif scope == "all":
                synced = await self.bot.tree.sync()
                msg = f"🌍 Synced **{len(synced)}** commands globally."
            else:
                return await ctx.send("❌ Usage: `!sync here` (this server) or `!sync all` (globally)")

            # Send in channel, DM, and log
            await ctx.send(msg)
            try:
                await ctx.author.send(msg)
            except discord.Forbidden:
                await ctx.send("⚠️ Could not DM you the result.")

            print(msg)  # or use logger.info(msg)

        except Exception as e:
            error_msg = f"❌ Sync failed: {e}"
            await ctx.send(error_msg)
            try:
                await ctx.author.send(error_msg)
            except discord.Forbidden:
                pass
            print(error_msg)  # or logger.error(error_msg)

async def setup(bot):
    await bot.add_cog(SyncCog(bot))
