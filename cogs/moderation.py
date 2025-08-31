import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Optional, Union, List
from utils.permissions import has_mod_permissions, can_moderate_target, can_bot_moderate_target
from config import Config



logger = logging.getLogger(__name__)

async def role_autocomplete(interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
    """Autocomplete function for role selection"""
    if not interaction.guild:
        return []
    
    # Get all roles except @everyone and bot roles
    roles = [role for role in interaction.guild.roles if role.name != "@everyone" and not role.managed]
    
    # Filter roles based on current input (case insensitive)
    if current:
        roles = [role for role in roles if current.lower() in role.name.lower()]
    
    # Sort by position (higher roles first) and limit to 25 (Discord limit)
    roles.sort(key=lambda r: r.position, reverse=True)
    
    return [
        discord.app_commands.Choice(name=role.name, value=role.name)
        for role in roles[:25]
    ]

class Moderation(commands.Cog):
    """Moderation commands for the bot"""
    CUSTOM_COLORS = {
            "red": "#ff0000",
            "orange": "#ff8800",
            "yellow": "#ffee00",
            "lime": "#20fc03",
            "green": "#089c00",
            "Cyan": "#00ffff",
            "blue": "#0044ff",
            "purple": "#8800ff",
            "pink": "#ff00bb",
            "darkred": "#8c0000",
            "darkorange": "#cc6600",
            "darkyellow": "#756c00",
            "darklime": "#2e9623",
            "darkgreen": "#044f00",
            "darkcyan": "#008080",
            "darkblue": "#001e8c",
            "darkpurple": "#300057",
            "darkpink": "#570047",
            "white": "#ffffff",
            "black": "#030000",
            "brown": "#874b20"
    }
            
    
    def __init__(self, bot):
        self.bot = bot
        self.muted_users = {}  # Simple in-memory storage for muted users
        

    
    def parse_time_duration(self, duration_str: str) -> Optional[int]:
        """
        Parse time duration string and return minutes
        Supports: m/min/mins/minute/minutes, h/hour/hours, d/day/days, w/week/weeks, mo/month/months
        Examples: 5m, 2h, 1d, 3w, 1mo
        """
        if not duration_str:
            return None
        
        # Remove spaces and convert to lowercase
        duration_str = duration_str.replace(" ", "").lower()
        
        # Regex pattern to match number followed by time unit
        pattern = r'^(\d+)\s*(m|min|mins|minute|minutes|h|hour|hours|d|day|days|w|week|weeks|mo|month|months)$'
        match = re.match(pattern, duration_str)
        
        if not match:
            return None
        
        amount = int(match.group(1))
        unit = match.group(2)
        
        # Convert to minutes
        if unit in ['m', 'min', 'mins', 'minute', 'minutes']:
            return amount
        elif unit in ['h', 'hour', 'hours']:
            return amount * 60
        elif unit in ['d', 'day', 'days']:
            return amount * 60 * 24
        elif unit in ['w', 'week', 'weeks']:
            return amount * 60 * 24 * 7
        elif unit in ['mo', 'month', 'months']:
            return amount * 60 * 24 * 30  # Approximate month as 30 days
        
        return None
    
    def format_duration(self, minutes: int) -> str:
        """Convert minutes to a human-readable duration string"""
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif minutes < 1440:  # Less than a day
            hours = minutes // 60
            remaining_mins = minutes % 60
            if remaining_mins == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''} and {remaining_mins} minute{'s' if remaining_mins != 1 else ''}"
        else:  # Days
            days = minutes // 1440
            remaining_hours = (minutes % 1440) // 60
            if remaining_hours == 0:
                return f"{days} day{'s' if days != 1 else ''}"
            else:
                return f"{days} day{'s' if days != 1 else ''} and {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
    
    async def _parse_role_input(self, guild: discord.Guild, role_input: str) -> Optional[discord.Role]:
        """Parse role input from mention or name"""
        # Try to parse role mention first
        role_mention_match = re.match(r'<@&(\d+)>', role_input.strip())
        if role_mention_match:
            role_id = int(role_mention_match.group(1))
            return guild.get_role(role_id)
        
        # Try to find by name (case insensitive)
        return discord.utils.find(lambda r: r.name.lower() == role_input.lower(), guild.roles)
    
    # Kick command (Prefix)
    @commands.command(name="kick")
    @has_mod_permissions()
    @commands.guild_only()
    async def kick_prefix(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """Kick a member from the server"""
        await self._kick_user(ctx, member, reason, ctx.author)
    
    # Kick command (Slash)
    @discord.app_commands.command(name="kick", description="Kick a member from the server")
    @discord.app_commands.describe(
        member="The member to kick",
        reason="Reason for kicking the member"
    )
    @discord.app_commands.default_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Kick a member from the server (slash command)"""
        await self._kick_user(interaction, member, reason, interaction.user)
    
    async def _kick_user(self, ctx_or_interaction, member: discord.Member, reason: str, moderator):
        """Internal method to handle kick functionality"""
        # Permission checks
        can_mod, mod_reason = await can_moderate_target(moderator, member)
        if not can_mod:
            await self._send_response(ctx_or_interaction, f"❌ {mod_reason}")
            return
        
        can_bot_mod, bot_reason = await can_bot_moderate_target(ctx_or_interaction.guild.me, member)
        if not can_bot_mod:
            await self._send_response(ctx_or_interaction, f"❌ {bot_reason}")
            return
        
        try:
            # Send DM to user before kicking
            try:
                embed = discord.Embed(
                    title="You have been kicked",
                    description=f"**Server:** {ctx_or_interaction.guild.name}\n**Reason:** {reason}",
                    color=Config.COLORS["warning"],
                    timestamp=datetime.utcnow()
                )
                await member.send(embed=embed)
            except:
                pass  # Ignore if DM fails
            
            # Kick the member
            await member.kick(reason=f"Kicked by {moderator}: {reason}")
            
            # Log the action
            logger.info(f"User {member} kicked by {moderator} for: {reason}")
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Member Kicked",
                description=f"**Member:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {moderator.mention}",
                color=Config.COLORS["moderation"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to kick this member!")
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while kicking the member!")
    

# Ban command (Prefix)
    @commands.command(name="ban")
    @has_mod_permissions()
    @commands.guild_only()
    async def ban_prefix(self, ctx, target: Union[discord.Member, discord.User, int], *, reason: str = "No reason provided"):
        """Ban a member or user ID from the server"""
        member = await self._resolve_target(target)
        if not member:
            return await ctx.send("❌ Could not find that user.")
        await self._ban_user(ctx, member, reason, ctx.author)
    
    # Ban command (Slash)
    @discord.app_commands.command(name="ban", description="Ban a member or user ID from the server")
    @discord.app_commands.describe(
        user="The member or user ID to ban",
        reason="Reason for banning the member"
    )
    @discord.app_commands.default_permissions(ban_members=True)
    async def ban_slash(self, interaction: discord.Interaction, user: str, reason: str = "No reason provided"):
        """Ban a member or user ID from the server (slash command)"""
        # user could be mention, raw ID, or already a resolved member
        target = None
        if user.isdigit():
            target = int(user)
        else:
            try:
                target = await commands.MemberConverter().convert(interaction, user)
            except:
                try:
                    target = await commands.UserConverter().convert(interaction, user)
                except:
                    target = None

        member = await self._resolve_target(target)
        if not member:
            return await interaction.response.send_message("❌ Could not find that user.", ephemeral=True)
        await self._ban_user(interaction, member, reason, interaction.user)
    
    async def _resolve_target(self, target: Union[discord.Member, discord.User, int]) -> Union[discord.Member, discord.User, None]:
        if isinstance(target, (discord.Member, discord.User)):
            return target
        try:
            return await self.bot.fetch_user(int(target))
        except Exception:
            return None
    
    async def _ban_user(self, ctx_or_interaction, member: Union[discord.Member, discord.User], reason: str, moderator):
        """Internal method to handle ban functionality"""
        if isinstance(member, discord.Member):
            can_mod, mod_reason = await can_moderate_target(moderator, member)
            if not can_mod:
                return await self._send_response(ctx_or_interaction, f"❌ {mod_reason}")
    
            can_bot_mod, bot_reason = await can_bot_moderate_target(ctx_or_interaction.guild.me, member)
            if not can_bot_mod:
                return await self._send_response(ctx_or_interaction, f"❌ {bot_reason}")
    
        try:
            # Send DM to user before banning
            try:
                embed = discord.Embed(
                    title="You have been banned",
                    description=f"**Server:** {ctx_or_interaction.guild.name}\n**Reason:** {reason}",
                    color=Config.COLORS["error"],
                    timestamp=datetime.utcnow()
                )
                await member.send(embed=embed)
            except:
                pass  # Ignore if DM fails
    
            # Ban the member
            await ctx_or_interaction.guild.ban(
                member,
                reason=f"Banned by {moderator}: {reason}",
                delete_message_days=1
            )
    
            # Log the action
            logger.info(f"User {member} banned by {moderator} for: {reason}")
    
            # Send confirmation
            embed = discord.Embed(
                title="🔨 Member Banned",
                description=f"**User:** {getattr(member, 'mention', str(member))}\n"
                            f"**Reason:** {reason}\n"
                            f"**Moderator:** {moderator.mention}",
                color=Config.COLORS["moderation"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
    
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to ban this user!")
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while banning the user!")



    @commands.command(name="vcmute")
    @commands.has_permissions(mute_members=True)
    @commands.guild_only()
    async def vcmute_prefix(self, ctx, member: discord.Member):
        """Mute a member in a voice channel"""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot mute someone with an equal or higher role.")

        try:
            await member.edit(mute=True, reason=f"Muted by {ctx.author}")
            await ctx.send(f"✅ Muted {member.display_name}")
        except:
            await ctx.send("❌ Failed to mute. Are they in a VC?")

    @discord.app_commands.command(name="vcmute", description="Mute a member in voice channel")
    @discord.app_commands.describe(member="The member to mute")
    async def vcmute_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot mute someone with an equal or higher role.", ephemeral=True)

        try:
            await member.edit(mute=True, reason=f"Muted by {interaction.user}")
            await interaction.response.send_message(f"✅ Muted {member.display_name}")
        except:
            await interaction.response.send_message("❌ Failed to mute. Are they in a VC?", ephemeral=True)

    @commands.command(name="vcunmute")
    @commands.has_permissions(mute_members=True)
    @commands.guild_only()
    async def vcunmute_prefix(self, ctx, member: discord.Member):
        """Unmute a member in a voice channel"""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot unmute someone with an equal or higher role.")

        try:
            await member.edit(mute=False, reason=f"Unmuted by {ctx.author}")
            await ctx.send(f"✅ Unmuted {member.display_name}")
        except:
            await ctx.send("❌ Failed to unmute. Are they in a VC?")

    @discord.app_commands.command(name="vcunmute", description="Unmute a member in voice channel")
    @discord.app_commands.describe(member="The member to unmute")
    async def vcunmute_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot unmute someone with an equal or higher role.", ephemeral=True)

        try:
            await member.edit(mute=False, reason=f"Unmuted by {interaction.user}")
            await interaction.response.send_message(f"✅ Unmuted {member.display_name}")
        except:
            await interaction.response.send_message("❌ Failed to unmute. Are they in a VC?", ephemeral=True)

    @commands.command(name="deafen")
    @commands.has_permissions(deafen_members=True)
    @commands.guild_only()
    async def deafen_prefix(self, ctx, member: discord.Member):
        """Deafen a member in a voice channel"""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot deafen someone with an equal or higher role.")

        try:
            await member.edit(deafen=True, reason=f"Deafened by {ctx.author}")
            await ctx.send(f"✅ Deafened {member.display_name}")
        except:
            await ctx.send("❌ Failed to deafen. Are they in a VC?")

    @discord.app_commands.command(name="deafen", description="Deafen a member in voice channel")
    @discord.app_commands.describe(member="The member to deafen")
    async def deafen_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot deafen someone with an equal or higher role.", ephemeral=True)

        try:
            await member.edit(deafen=True, reason=f"Deafened by {interaction.user}")
            await interaction.response.send_message(f"✅ Deafened {member.display_name}")
        except:
            await interaction.response.send_message("❌ Failed to deafen. Are they in a VC?", ephemeral=True)

    @commands.command(name="undeafen")
    @commands.has_permissions(deafen_members=True)
    @commands.guild_only()
    async def undeafen_prefix(self, ctx, member: discord.Member):
        """Undeafen a member in a voice channel"""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot undeafen someone with an equal or higher role.")

        try:
            await member.edit(deafen=False, reason=f"Undeafened by {ctx.author}")
            await ctx.send(f"✅ Undeafened {member.display_name}")
        except:
            await ctx.send("❌ Failed to undeafen. Are they in a VC?")

    @discord.app_commands.command(name="undeafen", description="Undeafen a member in voice channel")
    @discord.app_commands.describe(member="The member to undeafen")
    async def undeafen_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot undeafen someone with an equal or higher role.", ephemeral=True)

        try:
            await member.edit(deafen=False, reason=f"Undeafened by {interaction.user}")
            await interaction.response.send_message(f"✅ Undeafened {member.display_name}")
        except:
            await interaction.response.send_message("❌ Failed to undeafen. Are they in a VC?", ephemeral=True)

    @commands.command(name="disconnect")
    @commands.has_permissions(move_members=True)
    @commands.guild_only()
    async def disconnect_prefix(self, ctx, member: discord.Member):
        """Disconnect a member from voice channel"""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot disconnect someone with an equal or higher role.")

        try:
            await member.move_to(None, reason=f"Disconnected by {ctx.author}")
            await ctx.send(f"✅ Disconnected {member.display_name}")
        except:
            await ctx.send("❌ Failed to disconnect. Are they in a VC?")

    @discord.app_commands.command(name="disconnect", description="Disconnect a member from voice channel")
    @discord.app_commands.describe(member="The member to disconnect")
    async def disconnect_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot disconnect someone with an equal or higher role.", ephemeral=True)

        try:
            await member.move_to(None, reason=f"Disconnected by {interaction.user}")
            await interaction.response.send_message(f"✅ Disconnected {member.display_name}")
        except:
            await interaction.response.send_message("❌ Failed to disconnect. Are they in a VC?", ephemeral=True)

    @commands.command(name="move")
    @commands.has_permissions(move_members=True)
    @commands.guild_only()
    async def move_prefix(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        """Move a member to another voice channel"""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot move someone with an equal or higher role.")

        try:
            await member.move_to(channel, reason=f"Moved by {ctx.author}")
            await ctx.send(f"✅ Moved {member.display_name} to {channel.name}")
        except:
            await ctx.send("❌ Failed to move. Are they in a VC?")

    @discord.app_commands.command(name="move", description="Move a member to another voice channel")
    @discord.app_commands.describe(
        member="The member to move",
        channel="The voice channel to move them to"
    )
    async def move_slash(self, interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot move someone with an equal or higher role.", ephemeral=True)

        try:
            await member.move_to(channel, reason=f"Moved by {interaction.user}")
            await interaction.response.send_message(f"✅ Moved {member.display_name} to {channel.name}")
        except:
            await interaction.response.send_message("❌ Failed to move. Are they in a VC?", ephemeral=True)
    

    # Prefix command
    @commands.command(name="rolecolor")
    @commands.has_permissions(manage_roles=True)
    async def rolecolor_prefix(self, ctx, role: discord.Role, *, color: str):
        # Check role hierarchy
        if role >= ctx.author.top_role:
            await ctx.send("❌ You cannot change a role higher than or equal to your top role.")
            return
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot change a role higher than my top role.")
            return

        # Normalize color input
        color_input = color.strip().lower()
        hex_code = self.CUSTOM_COLORS.get(color_input)

        # Check if user typed a hex directly
        if hex_code is None:
            if color_input.startswith("#") and len(color_input) == 7:
                hex_code = color_input
            else:
                await ctx.send("❌ Invalid color! Use one of: " + ", ".join(self.CUSTOM_COLORS.keys()))
                return

        new_color = discord.Color(int(hex_code.lstrip("#"), 16))

        # Apply new color
        try:
            await role.edit(color=new_color, reason=f"Role color changed by {ctx.author}")
            await ctx.send(f"✅ Role `{role.name}` color changed to `{color.title()}`")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to change this role.")
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

        # ===============================
    # PREFIX COMMANDS
    # ===============================
    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock_prefix(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Lock a text channel"""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{channel.mention} has been **locked**.",
            color=random.choice([
                discord.Color.red(), discord.Color.orange(), discord.Color.blurple()
            ]),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Locked by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock_prefix(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Unlock a text channel"""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{channel.mention} has been **unlocked**.",
            color=random.choice([
                discord.Color.green(), discord.Color.blurple(), discord.Color.gold()
            ]),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Unlocked by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

        # ===============================
    # NICKNAME COMMANDS
    # ===============================

    # PREFIX COMMAND - Change Nickname
    @commands.command(name="nick", aliases=["nickname"])
    @commands.has_permissions(manage_nicknames=True)
    async def nick_prefix(self, ctx: commands.Context, member: discord.Member, *, nickname: str):
        """Change a member's nickname (mod only)."""
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot change the nickname of someone with an equal or higher role.")

        try:
            old_name = member.display_name
            await member.edit(nick=nickname)
            embed = discord.Embed(
                title="✏️ Nickname Changed",
                description=f"**{old_name}** ➝ **{nickname}**",
                color=discord.Color.blurple(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"Changed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I don’t have permission to change that user’s nickname.")

    # PREFIX COMMAND - Reset Nickname
    @commands.command(name="resetnick")
    @commands.has_permissions(manage_nicknames=True)
    async def resetnick_prefix(self, ctx: commands.Context, member: discord.Member):
        """Reset a member's nickname to default (mod only)."""
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot reset the nickname of someone with an equal or higher role.")

        try:
            await member.edit(nick=None)
            embed = discord.Embed(
                title="🔄 Nickname Reset",
                description=f"Nickname reset for {member.mention}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"Reset by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I don’t have permission to reset that user’s nickname.")

    # ===============================
    # SLASH COMMANDS
    # ===============================

    @app_commands.command(name="nick", description="Change a member's nickname (mod only).")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick_slash(self, interaction: discord.Interaction, member: discord.Member, nickname: str):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ You cannot change the nickname of someone with an equal or higher role.", ephemeral=True)

        try:
            old_name = member.display_name
            await member.edit(nick=nickname)
            embed = discord.Embed(
                title="✏️ Nickname Changed",
                description=f"**{old_name}** ➝ **{nickname}**",
                color=discord.Color.blurple(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"Changed by {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don’t have permission to change that user’s nickname.", ephemeral=True)

    @app_commands.command(name="resetnick", description="Reset a member's nickname (mod only).")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def resetnick_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ You cannot reset the nickname of someone with an equal or higher role.", ephemeral=True)

        try:
            await member.edit(nick=None)
            embed = discord.Embed(
                title="🔄 Nickname Reset",
                description=f"Nickname reset for {member.mention}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"Reset by {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don’t have permission to reset that user’s nickname.", ephemeral=True)



    # ===============================
    # SLASH COMMANDS
    # ===============================
    @app_commands.command(name="lock", description="Lock a text channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_slash(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{channel.mention} has been **locked**.",
            color=random.choice([
                discord.Color.red(), discord.Color.orange(), discord.Color.blurple()
            ]),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Locked by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="unlock", description="Unlock a text channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_slash(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{channel.mention} has been **unlocked**.",
            color=random.choice([
                discord.Color.green(), discord.Color.blurple(), discord.Color.gold()
            ]),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Unlocked by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    
    # -----------------------
    # Prefix command: list all colors
    # -----------------------
    @commands.command(name="rolecolors")
    async def list_colors_prefix(self, ctx):
        embed = discord.Embed(
            title="🎨 Available Role Colors",
            description="\n".join([f"• **{name}**" for name in self.CUSTOM_COLORS.keys()]),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    # -----------------------
    # Slash command: change role color
    # -----------------------
    @app_commands.command(name="rolecolor", description="Change a role's color using a dropdown")
    @app_commands.describe(role="Select a role to change", color="Pick a color")
    @app_commands.choices(color=[app_commands.Choice(name=name, value=name) for name in CUSTOM_COLORS])
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rolecolor_slash(self, interaction: discord.Interaction, role: discord.Role, color: app_commands.Choice[str]):
        if role >= interaction.user.top_role:
            await interaction.response.send_message(
                "❌ You cannot change a role higher than or equal to your top role.", ephemeral=True
            )
            return
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "❌ I cannot change a role higher than my top role.", ephemeral=True
            )
            return

        hex_code = self.CUSTOM_COLORS.get(color.value)
        new_color = discord.Color(int(hex_code.lstrip("#"), 16))

        try:
            await role.edit(color=new_color, reason=f"Role color changed by {interaction.user}")
            await interaction.response.send_message(f"✅ Role `{role.name}` color changed to `{color.value}`")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to change this role.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    # -----------------------
    # Slash command: list all colors
    # -----------------------
    @app_commands.command(name="rolecolors", description="List all available role colors")
    async def list_colors_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎨 Available Role Colors",
            description="\n".join([f"• **{name}**" for name in self.CUSTOM_COLORS.keys()]),
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # ===============================
    # PREFIX COMMAND
    # ===============================
    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode_prefix(self, ctx: commands.Context, seconds: int = 0):
        """Set slowmode in the current channel"""
        await ctx.channel.edit(slowmode_delay=seconds)

        embed = discord.Embed(
            title="🐢 Slowmode Updated",
            description=f"Slowmode set to **{seconds} seconds** in {ctx.channel.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Updated by {ctx.author}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    # ===============================
    # SLASH COMMAND
    # ===============================
    @app_commands.command(name="slowmode", description="Set the slowmode for this channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_slash(self, interaction: discord.Interaction, seconds: int = 0):
        await interaction.channel.edit(slowmode_delay=seconds)

        embed = discord.Embed(
            title="🐢 Slowmode Updated",
            description=f"Slowmode set to **{seconds} seconds** in {interaction.channel.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Updated by {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)
    
    # Clear messages command (Prefix)
    @commands.command(name="purge", aliases=["clear"])
    @has_mod_permissions()
    @commands.guild_only()
    async def clear_prefix(self, ctx, amount: int = 10):
        """Clear a specified number of messages"""
        await self._clear_messages(ctx, amount, ctx.author)
    
    # Clear messages command (Slash)
    @discord.app_commands.command(name="purge", description="Clear a specified number of messages")
    @discord.app_commands.describe(amount="Number of messages to clear (max 100)")
    @discord.app_commands.default_permissions(manage_messages=True)
    async def clear_slash(self, interaction: discord.Interaction, amount: int = 10):
        """Clear a specified number of messages (slash command)"""
        await self._clear_messages(interaction, amount, interaction.user)
    
    async def _clear_messages(self, ctx_or_interaction, amount: int, moderator):
        """Internal method to handle message clearing"""
        if amount <= 0:
            await self._send_response(ctx_or_interaction, "❌ Amount must be greater than 0!")
            return
        
        if amount > Config.MAX_MESSAGE_DELETE:
            await self._send_response(ctx_or_interaction, f"❌ Cannot delete more than {Config.MAX_MESSAGE_DELETE} messages at once!")
            return
        
        try:
            # Get the channel
            channel = ctx_or_interaction.channel
            
            # Delete messages
            if isinstance(ctx_or_interaction, commands.Context):
                # For prefix commands, include the command message in deletion
                messages = await channel.purge(limit=amount + 1)
                deleted_count = len(messages) - 1  # Subtract command message
            else:
                # For slash commands, don't include the interaction
                messages = await channel.purge(limit=amount)
                deleted_count = len(messages)
            
            # Log the action
            logger.info(f"{deleted_count} messages cleared by {moderator} in #{channel.name}")
            
            # Send confirmation (will auto-delete after 5 seconds)
            embed = discord.Embed(
                title="🧹 Messages Cleared",
                description=f"Deleted {deleted_count} messages",
                color=Config.COLORS["success"]
            )
            
            if isinstance(ctx_or_interaction, commands.Context):
                msg = await ctx_or_interaction.send(embed=embed)
                await asyncio.sleep(5)
                try:
                    await msg.delete()
                except:
                    pass
            else:
                await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to delete messages!")
        except Exception as e:
            logger.error(f"Error clearing messages: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while clearing messages!")

    # $deletechannel command
    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def deletechannel(self, ctx, channel: discord.TextChannel):
        await channel.delete()
        await ctx.send(f"✅ Channel {channel.name} has been deleted.")

    # Slash command version of deletechannel
    @discord.app_commands.command(name="deletechannel", description="Delete a channel")
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    async def slash_deletechannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await channel.delete()
        await interaction.response.send_message(f"✅ Channel {channel.name} has been deleted.")

    # $renamechannel command
    @commands.command(name="renamechannel")
    @commands.has_permissions(manage_channels=True)
    async def renamechannel(self, ctx, channel: discord.TextChannel, *, new_name: str):
        """Rename a channel"""
        await self._rename_channel(ctx, channel, new_name, ctx.author)

    # Slash command version of renamechannel
    @discord.app_commands.command(name="renamechannel", description="Rename a channel")
    @discord.app_commands.describe(
        channel="The channel to rename",
        new_name="The new name for the channel"
    )
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    async def slash_renamechannel(self, interaction: discord.Interaction, channel: discord.TextChannel, new_name: str):
        """Rename a channel (slash command)"""
        await self._rename_channel(interaction, channel, new_name, interaction.user)
    
    async def _rename_channel(self, ctx_or_interaction, channel: discord.TextChannel, new_name: str, moderator):
        """Internal method to handle channel renaming"""
        # Validate new name
        if len(new_name) < 1 or len(new_name) > 100:
            await self._send_response(ctx_or_interaction, "❌ Channel name must be between 1 and 100 characters!")
            return
        
        # Remove invalid characters and convert to lowercase with dashes
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9\-_]', '-', new_name.lower())
        clean_name = re.sub(r'-+', '-', clean_name).strip('-')
        
        if not clean_name:
            await self._send_response(ctx_or_interaction, "❌ Invalid channel name! Channel names can only contain letters, numbers, dashes, and underscores.")
            return
        
        old_name = channel.name
        
        try:
            # Rename the channel
            await channel.edit(name=clean_name, reason=f"Channel renamed by {moderator}")
            
            # Log the action
            logger.info(f"Channel {old_name} renamed to {clean_name} by {moderator}")
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Channel Renamed",
                description=f"**Old Name:** #{old_name}\n**New Name:** {channel.mention}\n**Moderator:** {moderator.mention}",
                color=Config.COLORS["success"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to manage channels!")
        except discord.HTTPException as e:
            if "already taken" in str(e).lower():
                await self._send_response(ctx_or_interaction, f"❌ A channel with the name `{clean_name}` already exists!")
            else:
                await self._send_response(ctx_or_interaction, f"❌ Failed to rename channel: {str(e)}")
        except Exception as e:
            logger.error(f"Error renaming channel: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while renaming the channel!")
    
    # Mute command (Prefix)
    @commands.command(name="mute")
    @has_mod_permissions()
    @commands.guild_only()
    async def mute_prefix(self, ctx, member: discord.Member, duration: Optional[str] = None, *, reason: str = "No reason provided"):
        """Mute a member (timeout) - Duration examples: 5m, 2h, 1d, 3w, 1mo"""
        # Parse duration string to minutes
        duration_minutes = None
        if duration:
            # Try parsing as time string first (5m, 2h, etc.)
            duration_minutes = self.parse_time_duration(duration)
            if duration_minutes is None:
                # If that fails, try parsing as plain number (backwards compatibility)
                try:
                    duration_minutes = int(duration)
                except ValueError:
                    await ctx.send("❌ Invalid duration format! Use examples like: 5m, 2h, 1d, 3w, 1mo")
                    return
        
        await self._mute_user(ctx, member, duration_minutes, reason, ctx.author)
    
    # Mute command (Slash)
    @discord.app_commands.command(name="mute", description="Mute a member using timeout")
    @discord.app_commands.describe(
        member="The member to mute",
        duration="Duration in minutes (default: 60, max: 40320)",
        reason="Reason for muting the member"
    )
    @discord.app_commands.default_permissions(moderate_members=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member, duration: Optional[int] = None, reason: str = "No reason provided"):
        """Mute a member using timeout (slash command)"""
        await self._mute_user(interaction, member, duration, reason, interaction.user)
    
    async def _mute_user(self, ctx_or_interaction, member: discord.Member, duration: Optional[int], reason: str, moderator):
        """Internal method to handle muting functionality"""
        # Permission checks
        can_mod, mod_reason = await can_moderate_target(moderator, member)
        if not can_mod:
            await self._send_response(ctx_or_interaction, f"❌ {mod_reason}")
            return
        
        can_bot_mod, bot_reason = await can_bot_moderate_target(ctx_or_interaction.guild.me, member)
        if not can_bot_mod:
            await self._send_response(ctx_or_interaction, f"❌ {bot_reason}")
            return
        
        # Set default duration if not provided
        if duration is None:
            duration = 60  # 60 minutes default
        
        # Validate duration (max 28 days = 40320 minutes)
        if duration <= 0 or duration > 40320:
            await self._send_response(ctx_or_interaction, "❌ Duration must be between 1 and 40320 minutes (28 days)!")
            return
        
        try:
            # Calculate timeout until (use timezone-aware datetime)
            timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
            
            # Apply timeout
            await member.timeout(timeout_until, reason=f"Muted by {moderator}: {reason}")
            
            # Log the action
            logger.info(f"User {member} muted by {moderator} for {duration} minutes: {reason}")
            
            # Send confirmation
            duration_text = self.format_duration(duration)
            embed = discord.Embed(
                title="🔇 Member Muted",
                description=f"**Member:** {member.mention}\n**Duration:** {duration_text}\n**Reason:** {reason}\n**Moderator:** {moderator.mention}",
                color=Config.COLORS["moderation"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to timeout this member!")
        except Exception as e:
            logger.error(f"Error muting user: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while muting the member!")
    
    # Unmute command (Prefix)
    @commands.command(name="unmute")
    @has_mod_permissions()
    @commands.guild_only()
    async def unmute_prefix(self, ctx, member: discord.Member):
        """Unmute a member"""
        await self._unmute_user(ctx, member, ctx.author)
    
    # Unmute command (Slash)
    @discord.app_commands.command(name="unmute", description="Unmute a member")
    @discord.app_commands.describe(member="The member to unmute")
    @discord.app_commands.default_permissions(moderate_members=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member):
        """Unmute a member (slash command)"""
        await self._unmute_user(interaction, member, interaction.user)
    
    async def _unmute_user(self, ctx_or_interaction, member: discord.Member, moderator):
        """Internal method to handle unmuting functionality"""
        try:
            # Remove timeout
            await member.timeout(None, reason=f"Unmuted by {moderator}")
            
            # Log the action
            logger.info(f"User {member} unmuted by {moderator}")
            
            # Send confirmation
            embed = discord.Embed(
                title="🔊 Member Unmuted",
                description=f"**Member:** {member.mention}\n**Moderator:** {moderator.mention}",
                color=Config.COLORS["success"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to remove timeout from this member!")
        except Exception as e:
            logger.error(f"Error unmuting user: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while unmuting the member!")
    
    # Unban command (Prefix)
    @commands.command(name="unban")
    @has_mod_permissions()
    @commands.guild_only()
    async def unban_prefix(self, ctx, user_id: int, *, reason: str = "No reason provided"):
        """Unban a user by their ID"""
        await self._unban_user(ctx, user_id, reason, ctx.author)
    
    # Unban command (Slash)
    @discord.app_commands.command(name="unban", description="Unban a user by their ID")
    @discord.app_commands.describe(
        user_id="The ID of the user to unban",
        reason="Reason for unbanning the user"
    )
    @discord.app_commands.default_permissions(ban_members=True)
    async def unban_slash(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        """Unban a user by their ID (slash command)"""
        try:
            user_id_int = int(user_id)
            await self._unban_user(interaction, user_id_int, reason, interaction.user)
        except ValueError:
            await self._send_response(interaction, "❌ Invalid user ID! Please provide a valid Discord user ID.")
    
    async def _unban_user(self, ctx_or_interaction, user_id: int, reason: str, moderator):
        """Internal method to handle unban functionality"""
        try:
            # Get the user object
            try:
                user = await ctx_or_interaction.client.fetch_user(user_id)
            except discord.NotFound:
                await self._send_response(ctx_or_interaction, "❌ User not found! Please check the user ID.")
                return
            except discord.HTTPException:
                await self._send_response(ctx_or_interaction, "❌ Failed to fetch user information.")
                return
            
            # Check if user is actually banned
            try:
                ban_entry = await ctx_or_interaction.guild.fetch_ban(user)
            except discord.NotFound:
                await self._send_response(ctx_or_interaction, f"❌ {user.mention} is not banned!")
                return
            
            # Unban the user
            await ctx_or_interaction.guild.unban(user, reason=f"Unbanned by {moderator}: {reason}")
            
            # Log the action
            logger.info(f"User {user} unbanned by {moderator} for: {reason}")
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Member Unbanned",
                description=f"**Member:** {user.mention} (`{user.id}`)\n**Reason:** {reason}\n**Moderator:** {moderator.mention}",
                color=Config.COLORS["success"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to unban members!")
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while unbanning the user!")
    
    # Add Role command (Prefix)
    @commands.command(name="giverole", aliases=["addrole"])
    @has_mod_permissions()
    @commands.guild_only()
    async def addrole_prefix(self, ctx, member: discord.Member, *, role_input: str):
        """Give a role to a member"""
        # Parse role from mention or name
        role = await self._parse_role_input(ctx.guild, role_input)
        if not role:
            await ctx.send(f"❌ Role '{role_input}' not found!")
            return
        await self._add_role(ctx, member, role, ctx.author)
    
    # Add Role command (Slash)
    @discord.app_commands.command(name="giverole", description="Give a role to a member")
    @discord.app_commands.describe(
        member="The member to give the role to",
        role="The role to give (searchable)"
    )
    @discord.app_commands.autocomplete(role=role_autocomplete)
    async def addrole_slash(self, interaction: discord.Interaction, member: discord.Member, role: str):
        """Give a role to a member (slash command)"""
        # Check permissions manually
        if not interaction.user.guild_permissions.manage_roles and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need Manage Roles permission to use this command!", ephemeral=True)
            return
        
        # Parse role from autocomplete selection
        role_obj = await self._parse_role_input(interaction.guild, role)
        if not role_obj:
            await interaction.response.send_message(f"❌ Role '{role}' not found!", ephemeral=True)
            return
        await self._add_role(interaction, member, role_obj, interaction.user)
    
    async def _add_role(self, ctx_or_interaction, member: discord.Member, role: discord.Role, moderator):
        """Internal method to handle adding roles"""
        
        # Check if member already has the role
        if role in member.roles:
            await self._send_response(ctx_or_interaction, f"❌ {member.mention} already has the role **{role.name}**!")
            return
        
        # Permission checks
        can_mod, mod_reason = await can_moderate_target(moderator, member)
        if not can_mod:
            await self._send_response(ctx_or_interaction, f"❌ {mod_reason}")
            return
        
        # Check if moderator can manage this role
        if role >= moderator.top_role and moderator != ctx_or_interaction.guild.owner:
            await self._send_response(ctx_or_interaction, f"❌ You cannot manage the role **{role.name}** as it's equal or higher than your highest role!")
            return
        
        # Check if bot can manage this role
        if role >= ctx_or_interaction.guild.me.top_role:
            await self._send_response(ctx_or_interaction, f"❌ Bot cannot manage the role **{role.name}** as it's equal or higher than bot's highest role!")
            return
        
        try:
            # Add the role
            await member.add_roles(role, reason=f"Role added by {moderator}")
            
            # Log the action
            logger.info(f"Role {role.name} added to {member} by {moderator}")
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Role Added",
                description=f"**Member:** {member.mention}\n**Role:** {role.mention}\n**Moderator:** {moderator.mention}",
                color=Config.COLORS["success"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to manage roles!")
        except Exception as e:
            logger.error(f"Error adding role: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while adding the role!")

    # -----------------
    # PREFIX COMMAND
    # -----------------
    @commands.command(name="rolerename")
    @commands.has_permissions(manage_roles=True)
    async def role_rename_prefix(self, ctx, role: discord.Role, *, new_name: str):
        """Rename a role (prefix command)."""
        # Prevent renaming higher roles
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot rename a role higher or equal to your top role.")

        try:
            old_name = role.name
            await role.edit(
                name=new_name,
                reason=f"Responsible moderator {ctx.author} ({ctx.author.id})"
            )
            await ctx.send(f"✅ Renamed role **{old_name}** → **{new_name}**")

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to edit that role.")
        except discord.HTTPException:
            await ctx.send("❌ Failed to rename the role.")

    # -----------------
    # SLASH COMMAND
    # -----------------
    @app_commands.command(name="rolerename", description="Rename a role (Admin only).")
    @app_commands.describe(role="The role to rename", newname="The new name for the role")
    async def role_rename_slash(self, interaction: discord.Interaction, role: discord.Role, newname: str):
        # Check if user has permissions
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_roles):
            return await interaction.response.send_message("❌ You don't have permission to do that.", ephemeral=True)

        # Prevent renaming higher roles
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ You cannot rename a role higher or equal to your top role.", ephemeral=True)

        try:
            old_name = role.name
            await role.edit(
                name=newname,
                reason=f"Responsible moderator {interaction.user} ({interaction.user.id})"
            )
            await interaction.response.send_message(f"✅ Renamed role **{old_name}** → **{newname}**")

        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to edit that role.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("❌ Failed to rename the role.", ephemeral=True)

    
    # Remove Role command (Prefix)
    @commands.command(name="takerole", aliases=["removerole"])
    @has_mod_permissions()
    @commands.guild_only()
    async def removerole_prefix(self, ctx, member: discord.Member, *, role_input: str):
        """Remove a role from a member"""
        # Parse role from mention or name
        role = await self._parse_role_input(ctx.guild, role_input)
        if not role:
            await ctx.send(f"❌ Role '{role_input}' not found!")
            return
        await self._remove_role(ctx, member, role, ctx.author)
    
    # Remove Role command (Slash)
    @discord.app_commands.command(name="takerole", description="Remove a role from a member")
    @discord.app_commands.describe(
        member="The member to remove the role from",
        role="The role to remove (searchable)"
    )
    @discord.app_commands.autocomplete(role=role_autocomplete)
    async def removerole_slash(self, interaction: discord.Interaction, member: discord.Member, role: str):
        """Remove a role from a member (slash command)"""
        # Check permissions manually
        if not interaction.user.guild_permissions.manage_roles and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need Manage Roles permission to use this command!", ephemeral=True)
            return
        
        # Parse role from autocomplete selection
        role_obj = await self._parse_role_input(interaction.guild, role)
        if not role_obj:
            await interaction.response.send_message(f"❌ Role '{role}' not found!", ephemeral=True)
            return
        await self._remove_role(interaction, member, role_obj, interaction.user)
    
    async def _remove_role(self, ctx_or_interaction, member: discord.Member, role: discord.Role, moderator):
        """Internal method to handle removing roles"""
        
        # Check if member has the role
        if role not in member.roles:
            await self._send_response(ctx_or_interaction, f"❌ {member.mention} doesn't have the role **{role.name}**!")
            return
        
        # Permission checks
        can_mod, mod_reason = await can_moderate_target(moderator, member)
        if not can_mod:
            await self._send_response(ctx_or_interaction, f"❌ {mod_reason}")
            return
        
        # Check if moderator can manage this role
        if role >= moderator.top_role and moderator != ctx_or_interaction.guild.owner:
            await self._send_response(ctx_or_interaction, f"❌ You cannot manage the role **{role.name}** as it's equal or higher than your highest role!")
            return
        
        # Check if bot can manage this role
        if role >= ctx_or_interaction.guild.me.top_role:
            await self._send_response(ctx_or_interaction, f"❌ Bot cannot manage the role **{role.name}** as it's equal or higher than bot's highest role!")
            return
        
        try:
            # Remove the role
            await member.remove_roles(role, reason=f"Role removed by {moderator}")
            
            # Log the action
            logger.info(f"Role {role.name} removed from {member} by {moderator}")
            
            # Send confirmation
            embed = discord.Embed(
                title="🗑️ Role Removed",
                description=f"**Member:** {member.mention}\n**Role:** {role.mention}\n**Moderator:** {moderator.mention}",
                color=Config.COLORS["warning"],
                timestamp=datetime.utcnow()
            )
            await self._send_response(ctx_or_interaction, embed=embed)
            
        except discord.Forbidden:
            await self._send_response(ctx_or_interaction, "❌ I don't have permission to manage roles!")
        except Exception as e:
            logger.error(f"Error removing role: {e}")
            await self._send_response(ctx_or_interaction, "❌ An error occurred while removing the role!")
    
    # List Roles command (Prefix)
    @commands.command(name="listroles", aliases=["roles"])
    @commands.guild_only()
    async def listroles_prefix(self, ctx):
        """List all roles in the server"""
        await self._list_roles(ctx)
    
    # List Roles command (Slash)
    @discord.app_commands.command(name="listroles", description="List all roles in the server")
    async def listroles_slash(self, interaction: discord.Interaction):
        """List all roles in the server (slash command)"""
        await self._list_roles(interaction)
    
    async def _list_roles(self, ctx_or_interaction):
        """Internal method to handle listing roles"""
        guild = ctx_or_interaction.guild
        
        # Get all roles except @everyone
        roles = [role for role in guild.roles if role.name != "@everyone"]
        
        if not roles:
            await self._send_response(ctx_or_interaction, "❌ No roles found in this server!")
            return
        
        # Sort roles by position (highest first)
        roles.sort(key=lambda r: r.position, reverse=True)
        
        # Create embed
        embed = discord.Embed(
            title=f"📋 Roles in {guild.name}",
            color=Config.COLORS["info"],
            timestamp=datetime.utcnow()
        )
        
        # Split roles into chunks to avoid Discord's field value limit
        role_chunks = []
        current_chunk = []
        current_length = 0
        
        for role in roles:
            # Format: @RoleName (ID: 123456789) - X members
            role_info = f"{role.mention} (ID: `{role.id}`) - {len(role.members)} member{'s' if len(role.members) != 1 else ''}"
            
            # Check if adding this role would exceed Discord's 1024 character limit
            if current_length + len(role_info) + 1 > 1024:
                role_chunks.append("\n".join(current_chunk))
                current_chunk = [role_info]
                current_length = len(role_info)
            else:
                current_chunk.append(role_info)
                current_length += len(role_info) + 1
        
        # Add remaining roles
        if current_chunk:
            role_chunks.append("\n".join(current_chunk))
        
        # Add fields to embed
        for i, chunk in enumerate(role_chunks):
            field_name = "Roles" if i == 0 else f"Roles (continued {i+1})"
            embed.add_field(name=field_name, value=chunk, inline=False)
        
        # Add footer with total count
        embed.set_footer(text=f"Total roles: {len(roles)} | Highest role: {roles[0].name if roles else 'None'}")
        
        await self._send_response(ctx_or_interaction, embed=embed)
    
    async def _send_response(self, ctx_or_interaction, content=None, *, embed=None):
        """Send response to either prefix command or slash command"""
        if isinstance(ctx_or_interaction, commands.Context):
            if embed:
                await ctx_or_interaction.send(embed=embed)
            else:
                await ctx_or_interaction.send(content)
        else:
            if ctx_or_interaction.response.is_done():
                if embed:
                    await ctx_or_interaction.followup.send(embed=embed)
                else:
                    await ctx_or_interaction.followup.send(content)
            else:
                if embed:
                    await ctx_or_interaction.response.send_message(embed=embed)
                else:
                    await ctx_or_interaction.response.send_message(content)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
