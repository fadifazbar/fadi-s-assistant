import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

# Try importing Config, fallback if missing
try:
    from config import Config
    PREFIX = Config.PREFIX
    COLORS = Config.COLORS
except ImportError:
    PREFIX = "$"
    COLORS = {"info": discord.Color.blue()}


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Help command (Prefix) ---
    @commands.command(name="help", aliases=["cmds", "cmnds", "command", "commands"])
    async def help_prefix(self, ctx, command_name: str = None):
        await self._show_help(ctx, command_name)

    # --- Help command (Slash) ---
    @app_commands.command(name="help", description="Show help information")
    @app_commands.describe(command="Specific command to get help for")
    async def help_slash(self, interaction: discord.Interaction, command: str = None):
        await self._show_help(interaction, command)

    # --- Internal helper ---
    async def _show_help(self, ctx_or_interaction, command_name: str = None):
        embed = discord.Embed(
            title="🤖 Bot Help",
            color=Config.COLORS.get("info", discord.Color.blue()),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Prefix: {Config.PREFIX} | Slash commands also available")

        # --- All commands info ---
        commands_info = {
            "kick": ("🦵 Kick", f"`{Config.PREFIX}kick <member> [reason]` or `/kick`\nKick a member from the server"),
            "ban": ("🔨 Ban", f"`{Config.PREFIX}ban <member> [reason]` or `/ban`\nBan a member from the server"),
            "mute": ("🔇 Mute", f"`{Config.PREFIX}mute <member> [duration] [reason]` or `/mute`\nMute a member (ex: 5m,2h,1d)"),
            "unmute": ("🔊 Unmute", f"`{Config.PREFIX}unmute <member>` or `/unmute`\nRemove timeout from a member"),
            "unban": ("✅ Unban", f"`{Config.PREFIX}unban <user_id> [reason]` or `/unban`\nUnban a user by ID"),
            "purge": ("🧹 Purge", f"`{Config.PREFIX}purge <amount>` or `/purge`\nDelete messages (default: 10, max: 100)"),
            "say": ("💬 Say", f"`{Config.PREFIX}say <message>` or `/say`\nMake the bot say something"),
            "giverole": ("➕ Give Role", f"`{Config.PREFIX}giverole <member> <role_name>` or `/giverole`\nGive a role"),
            "takerole": ("➖ Remove Role", f"`{Config.PREFIX}takerole <member> <role_name>` or `/takerole`\nRemove a role"),
            "deletechannel": ("🗑️ Delete Channel", f"`{Config.PREFIX}deletechannel <channel>` or `/deletechannel`\nRemove a channel"),
            "renamechannel": ("✏️ Rename Channel", f"`{Config.PREFIX}renamechannel <channel> <new_name>` or `/renamechannel`\nRename a channel"),
            "listroles": ("📜 List Roles", f"`{Config.PREFIX}listroles` or `/listroles`\nList all roles"),
            "saylogs": ("📝 Say Logs", f"`{Config.PREFIX}saylogs <message>` or `/saylogs`\nSend logs for the say command"),
            "snipe": ("🕵️‍♂️ Snipe", f"`{Config.PREFIX}snipe` or `/snipe`\nSee the last deleted message"),
            "editsnipe": ("✏️ Edit Snipe", f"`{Config.PREFIX}editsnipe` or `/editsnipe`\nSee the last edited message"),
            "ship": ("💘 Ship", f"`{Config.PREFIX}ship <member1> <member2>` or `/ship`\nShip two users"),
            "randomnumber": ("🎲 Random Number", f"`{Config.PREFIX}randomnumber <max>` or `/randomnumber`\nGenerate a random number"),
            "kiss": ("😘 Kiss", f"`{Config.PREFIX}kiss <member>` or `/kiss`\nKiss a member"),
            "invite": ("🔗 Invite", f"`{Config.PREFIX}invite` or `/invite`\nGet the bot invite link"),
            "ping": ("🏓 Ping", f"`{Config.PREFIX}ping` or `/ping`\nCheck bot latency"),
            "info": ("ℹ️ Info", f"`{Config.PREFIX}info` or `/info`\nGet bot information"),
            "avatar": ("🖼️ Avatar", f"`{Config.PREFIX}avatar <member>` or `/avatar`\nShow a user's avatar"),
            "8ball": ("🎱 8Ball", f"`{Config.PREFIX}8ball <question>` or `/8ball`\nPlay a game of 8ball"),
            "rolerename": ("📝 RoleRename", f"`{Config.PREFIX}rolerename <role> <new name>` or `/rolerename`\nRename a role in the server"),
            "tictactoe": ("❌⭕ TicTacToe", f"`{Config.PREFIX}xoxo <member>` or `/tictactoe`\nPlay TicTacToe with another user"),
            "rolecolor": ("🖍️ RoleColor", f"`{Config.PREFIX}rolecolor <role> <color>` or `/rolecolor`\nRecolor any role"),
            "rolecolors": ("🌈 RoleColors", f"`{Config.PREFIX}rolecolors` or `/rolecolors`\nShows a list of available colors"),
            "reactionrole": ("🎭 ReactionRole", f"`{Config.PREFIX}reactionrole <msg_id> <emoji> <role>` or `/reactionrole`\nAdd a reaction role"),
            "saychecklogs": ("💬 SayCheckLogs", f"`{Config.PREFIX}saychecklogs` or `/saychecklogs`\nCheck say command logs"),
            "serverinfo": ("❓ ServerInfo", f"`{Config.PREFIX}serverinfo` or `/serverinfo`\nCheck info about the server"),
            "coinflip": ("💲 CoinFlip", f"`{Config.PREFIX}coinflip` or `/coinflip`\nFlip a coin"),
            "userinfo": ("🎭 UserInfo", f"`{Config.PREFIX}userinfo <member>` or `/userinfo`\nGet user info"),
            "banner": ("🖼 Banner", f"`{Config.PREFIX}banner <member>` or `/banner`\nGet user banner"),
            "urldownload": ("🔗 UrlDownload", f"`{Config.PREFIX}urldownload <url>` or `/urldownload`\nDownload a video"),
            "nick": ("🎨 Nick", f"`{Config.PREFIX}nick <member> <name>` or `/nick`\nChange nickname"),
            "resetnick": ("🎨 ResetNick", f"`{Config.PREFIX}resetnick <member>` or `/resetnick`\nReset nickname"),
            "slowmode": ("🐌 Slowmode", f"`{Config.PREFIX}slowmode <seconds>` or `/slowmode`\nSet slowmode"),
            "lock": ("🔒 Lock", f"`{Config.PREFIX}lock <channel>` or `/lock`\nLock channel"),
            "unlock": ("🔓 Unlock", f"`{Config.PREFIX}unlock <channel>` or `/unlock`\nUnlock channel"),
            "deathbattle": ("💥 DeathBattle", f"`{Config.PREFIX}deathbattle <m1> <m2>` or `/deathbattle`\nBattle to death"),
            "hug": ("🤗 Hug", f"`{Config.PREFIX}hug <member>` or `/hug`\nHug someone"),
            "slap": ("👋 Slap", f"`{Config.PREFIX}slap <member>` or `/slap`\nSlap someone"),
            "punch": ("👊 Punch", f"`{Config.PREFIX}punch <member>` or `/punch`\nPunch someone"),
            "pat": ("🐶 Pat", f"`{Config.PREFIX}pat <member>` or `/pat`\nPat someone"),
            "forcekiss": ("💋 ForceKiss", f"`{Config.PREFIX}forcekiss <m1> <m2>` or `/forcekiss`\nForce two members to kiss"),
            "translate": ("🌐 Translate", f"`{Config.PREFIX}translate <lang>`\nTranslate messages"),
            "skibidi": ("🚽 Skibidi", f"`{Config.PREFIX}skibidi <member>` or `/skibidi`\nBattle in Skibidi"),
            "skibidilist": ("📃 SkibidiList", f"`{Config.PREFIX}skibidilist` or `/skibidilist`\nList Skibidi chars"),
            "marry": ("💍 Marry", f"`{Config.PREFIX}marry <member>` or `/marry`\nMarry someone"),
            "divorce": ("💔 Divorce", f"`{Config.PREFIX}divorce` or `/divorce`\nDivorce your partner"),
            "adopt": ("👼 Adopt", f"`{Config.PREFIX}adopt <member>` or `/adopt`\nAdopt a child"),
            "disown": ("😭 Disown", f"`{Config.PREFIX}disown` or `/disown`\nDisown a child"),
            "runaway": ("💨 RunAway", f"`{Config.PREFIX}runaway` or `/runaway`\nRun away"),
            "makeout": ("😘 MakeOut", f"`{Config.PREFIX}makeout <member>` or `/makeout`\nMake out with someone"),
            "play": ("▶️ Play", f"`{Config.PREFIX}play <song>` or `/play`\nPlay music"),
            "queue": ("📃 Queue", f"`{Config.PREFIX}queue` or `/queue`\nShow music queue"),
            "skip": ("⏭️ Skip", f"`{Config.PREFIX}skip` or `/skip`\nSkip song"),
            "pause": ("⏸ Pause", f"`{Config.PREFIX}pause` or `/pause`\nPause music"),
            "resume": ("▶️ Resume", f"`{Config.PREFIX}resume` or `/resume`\nResume music"),
            "nowplaying": ("🎶 NowPlaying", f"`{Config.PREFIX}nowplaying` or `/nowplaying`\nShow current song"),
            "stopmusic": ("⏹ Stop", f"`{Config.PREFIX}stopmusic` or `/stopmusic`\nStop music"),
            "loop": ("🔁 Loop", f"`{Config.PREFIX}loop` or `/loop`\nLoop playback"),
            "shuffle": ("🔀 Shuffle", f"`{Config.PREFIX}shuffle` or `/shuffle`\nShuffle queue"),
        }

        # --- Specific command help ---
        if command_name:
            cmd_key = command_name.lower()
            if cmd_key in commands_info:
                name, desc = commands_info[cmd_key]
                embed.add_field(name=name, value=desc, inline=False)
            else:
                embed.description = f"❌ Command `{command_name}` not found!"
        else:
            # --- General help grouped ---
            embed.description = f"A powerful moderation bot with both prefix (`{Config.PREFIX}`) and slash (`/`) commands."

            embed.add_field(
                name="🛡️ Moderation Commands",
                value=(
                    f"`{Config.PREFIX}kick`, `{Config.PREFIX}ban`, `{Config.PREFIX}unban`\n"
                    f"`{Config.PREFIX}mute`, `{Config.PREFIX}unmute`, `{Config.PREFIX}purge`\n"
                    f"`{Config.PREFIX}giverole`, `{Config.PREFIX}takerole`\n"
                    f"`{Config.PREFIX}deletechannel`, `{Config.PREFIX}renamechannel`\n"
                    f"`{Config.PREFIX}listroles`, `{Config.PREFIX}rolerename`, `{Config.PREFIX}rolecolor`\n"
                    f"`{Config.PREFIX}rolecolors`, `{Config.PREFIX}reactionrole`\n"
                    f"`{Config.PREFIX}saylogs`, `{Config.PREFIX}saychecklogs`\n"
                    f"`{Config.PREFIX}nick`, `{Config.PREFIX}resetnick`\n"
                    f"`{Config.PREFIX}slowmode`, `{Config.PREFIX}lock`, `{Config.PREFIX}unlock`"
                ),
                inline=False
            )

            embed.add_field(
                name="💬 General Commands",
                value=(
                    f"`{Config.PREFIX}say`, `{Config.PREFIX}help`, `{Config.PREFIX}ping`\n"
                    f"`{Config.PREFIX}info`, `{Config.PREFIX}avatar`, `{Config.PREFIX}8ball`\n"
                    f"`{Config.PREFIX}ship`, `{Config.PREFIX}snipe`, `{Config.PREFIX}editsnipe`\n"
                    f"`{Config.PREFIX}randomnumber`, `{Config.PREFIX}invite`, `{Config.PREFIX}kiss`\n"
                    f"`{Config.PREFIX}tictactoe`, `{Config.PREFIX}serverinfo`, `{Config.PREFIX}coinflip`\n"
                    f"`{Config.PREFIX}userinfo`, `{Config.PREFIX}banner`, `{Config.PREFIX}urldownload`\n"
                    f"`{Config.PREFIX}deathbattle`, `{Config.PREFIX}hug`, `{Config.PREFIX}slap`\n"
                    f"`{Config.PREFIX}punch`, `{Config.PREFIX}pat`, `{Config.PREFIX}forcekiss`\n"
                    f"`{Config.PREFIX}translate`, `{Config.PREFIX}skibidi`, `{Config.PREFIX}skibidilist`\n"
                    f"`{Config.PREFIX}marry`, `{Config.PREFIX}divorce`, `{Config.PREFIX}adopt`\n"
                    f"`{Config.PREFIX}disown`, `{Config.PREFIX}runaway`, `{Config.PREFIX}makeout`"
                ),
                inline=False
            )

            embed.add_field(
                name="🎶 Music Commands",
                value=(
                    f"`{Config.PREFIX}play`, `{Config.PREFIX}queue`, `{Config.PREFIX}skip`\n"
                    f"`{Config.PREFIX}pause`, `{Config.PREFIX}resume`, `{Config.PREFIX}nowplaying`\n"
                    f"`{Config.PREFIX}stopmusic`, `{Config.PREFIX}loop`, `{Config.PREFIX}shuffle`"
                ),
                inline=False
            )

            embed.add_field(
                name="ℹ️ Usage Notes",
                value="• All commands work with `/` slash commands too\n"
                      "• Moderation commands require appropriate permissions\n"
                      f"• Use `{Config.PREFIX}help <command>` for detailed help",
                inline=False
            )

        # --- Send embed safely ---
        await self._send_response(ctx_or_interaction, embed=embed)

    # --- Safe send helper ---
    async def _send_response(self, ctx_or_interaction, embed: discord.Embed = None, ephemeral: bool = False):
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(embed=embed)
        elif isinstance(ctx_or_interaction, discord.Interaction):
            if not ctx_or_interaction.response.is_done():
                await ctx_or_interaction.response.send_message(embed=embed, ephemeral=ephemeral)
            else:
                await ctx_or_interaction.followup.send(embed=embed, ephemeral=ephemeral)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))