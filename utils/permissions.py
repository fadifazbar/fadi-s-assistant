import discord
from discord.ext import commands
from typing import Union

def has_mod_permissions():
    """Check if user has moderation permissions"""
    async def predicate(ctx):
        if isinstance(ctx, commands.Context):
            # For prefix commands
            member = ctx.author
            guild = ctx.guild
        else:
            # For slash commands (interaction)
            member = ctx.user
            guild = ctx.guild
            # Convert user to member for permissions check
            if guild and isinstance(member, discord.User):
                member = guild.get_member(member.id)
                if not member:
                    return False
        
        if not guild or not member:
            return False
        
        # Bot owner always has permission
        if hasattr(ctx, 'bot') and member.id == ctx.bot.owner_id:
            return True
        
        # Check for administrator permission
        if member.guild_permissions.administrator:
            return True
        
        # Check for moderation permissions
        perms = member.guild_permissions
        return any([
            perms.kick_members,
            perms.ban_members,
            perms.manage_messages,
            perms.manage_roles
        ])
    
    return commands.check(predicate)

async def can_moderate_target(moderator: discord.Member, target: discord.Member) -> tuple[bool, str]:
    """
    Check if moderator can moderate the target user based on role hierarchy
    Returns (can_moderate: bool, reason: str)
    """
    if moderator == target:
        return False, "You cannot moderate yourself!"
    
    # Server owner cannot be moderated (except by server owner)
    if target == target.guild.owner and moderator != target.guild.owner:
        return False, "Cannot moderate the server owner!"
    
    # Check role hierarchy using position (server owner can moderate anyone)
    if moderator.top_role.position <= target.top_role.position and moderator != moderator.guild.owner:
        return False, "You cannot moderate users with equal or higher role positions!"
    
    return True, ""

async def can_bot_moderate_target(bot_member: discord.Member, target: discord.Member) -> tuple[bool, str]:
    """
    Check if bot can moderate the target user based on its highest role position
    Returns (can_moderate: bool, reason: str)
    """
    # Server owner cannot be moderated
    if target == target.guild.owner:
        return False, "Cannot moderate the server owner!"
    
    # Get bot's highest role position (top_role gives the highest role)
    # Bot must have higher role position than target
    if bot_member.top_role.position <= target.top_role.position:
        return False, f"Bot's highest role position ({bot_member.top_role.position}) is not high enough to moderate this user (position {target.top_role.position})!"
    
    return True, ""
