# cogs/deathbattle.py
# Requires: pip install -U discord.py pillow aiohttp

import asyncio
import io
import random
from typing import List, Tuple

import discord
from discord.ext import commands

from PIL import Image

# ------------ STATIC CONFIG (tweak to match your header image) ------------
HEADER_PATH = "deathbattle_header.png"  # your static header (like the one you sent)

# (x, y, size) for each PFP square on the header image
# -> top-left corner (x,y) and a square "size" in pixels
# Adjust these so the avatars sit perfectly in the white squares.
PFP1_BOX = (120, 280, 260)   # left box
PFP2_BOX = (975, 280, 260)   # right box

# Emojis (yours)
EMOJI_HEALTH      = "<:health_emoji:1408622054734958664>"
EMOJI_DB          = "<:deathbattle:1408624946858426430>"
EMOJI_WINNER      = "<:deathbattle_winner:1408624915388563467>"
EMOJI_BATTLE_LINE = "<:battle_emoji:1408620699349946572>"

# Starting HP and timings
START_HP = 100
TITLE_SHOW_SECONDS = 5                   # keep "Death Battle" title for 5s
TURN_DELAY_RANGE = (1.0, 1.5)            # time between turns
FIELD_TO_LOG_DELAY_RANGE = (0.3, 0.5)    # small delay before log line appears

# Embed limits
EMBED_DESC_LIMIT = 4096
DESC_SAFE_BUDGET = 3800  # start trimming once description would exceed this


# Weighted attack table (rarer => stronger)
# name, damage, weight    (weight = probability weight; higher weight = more common)
ATTACKS: List[Tuple[str, int, int]] = [
    ("punch",      8,  30),
    ("kick",       12, 25),
    ("headbutt",   15, 17),
    ("slash",      20, 12),
    ("shot",       25,  9),
    ("ULTIMATE",   35,  7),
]
# ---------------------------------------------------------------------------


def _square_avatar_crop(img: Image.Image, size: int) -> Image.Image:
    """Resize and center-crop avatar to a square of 'size'."""
    img = img.convert("RGBA")
    w, h = img.size
    # center crop to square
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
    return img.resize((size, size), Image.LANCZOS)


async def _compose_header_with_pfps(u1: discord.User, u2: discord.User) -> io.BytesIO:
    """Make one PNG: static header + both users' avatars pasted in the two squares."""
    # Load header
    header = Image.open(HEADER_PATH).convert("RGBA")

    # Read avatars (bytes) then PIL
    a1_bytes = await u1.display_avatar.replace(format="png", size=512).read()
    a2_bytes = await u2.display_avatar.replace(format="png", size=512).read()
    p1 = Image.open(io.BytesIO(a1_bytes))
    p2 = Image.open(io.BytesIO(a2_bytes))

    # Fit to squares
    x1, y1, s1 = PFP1_BOX
    x2, y2, s2 = PFP2_BOX
    p1_fit = _square_avatar_crop(p1, s1)
    p2_fit = _square_avatar_crop(p2, s2)

    # Paste (no HP or text drawn; image never changes during fight)
    header.alpha_composite(p1_fit, (x1, y1))
    header.alpha_composite(p2_fit, (x2, y2))

    out = io.BytesIO()
    header.save(out, format="PNG")
    out.seek(0)
    return out


def _pick_attack() -> Tuple[str, int]:
    """Return (attack_name, damage) using weights."""
    names, damages, weights = zip(*ATTACKS)
    idx = random.choices(range(len(ATTACKS)), weights=weights, k=1)[0]
    return names[idx], damages[idx]


def _trim_desc(lines: List[str]) -> List[str]:
    """Ensure lines joined won't exceed ~DESC_SAFE_BUDGET; drop oldest until safe."""
    while True:
        s = "\n".join(lines)
        if len(s) <= DESC_SAFE_BUDGET:
            return lines
        if lines:
            lines.pop(0)
        else:
            return lines


class DeathBattle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="deathbattle", description="Start a Death Battle between two users.")
    async def deathbattle(self, ctx: commands.Context, user1: discord.Member, user2: discord.Member):
        """Hybrid => works as $deathbattle / /deathbattle"""
        # Compose the static banner w/ PFPs
        banner_png = await _compose_header_with_pfps(user1, user2)
        banner_file = discord.File(banner_png, filename="deathbattle.png")

        # Build initial embed
        title_text = f"{EMOJI_DB} Death Battle"
        desc_lines: List[str] = []  # combat log lines live here

        embed = discord.Embed(title=title_text, color=discord.Color.red())
        embed.description = "\n".join(desc_lines)
        embed.set_image(url="attachment://deathbattle.png")

        # HP fields
        hp1, hp2 = START_HP, START_HP
        embed.add_field(name=f"{user1.name}", value=f"{EMOJI_HEALTH} {hp1}", inline=True)
        embed.add_field(name=f"{user2.name}", value=f"{EMOJI_HEALTH} {hp2}", inline=True)

        # Send (as one message; everything after this is edits)
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(file=banner_file, embed=embed)
            msg = await ctx.original_response()
        else:
            msg = await ctx.send(file=banner_file, embed=embed)

        # Keep title for 5 seconds, then clear it (image remains)
        await asyncio.sleep(TITLE_SHOW_SECONDS)
        embed.title = ""  # clear only the title
        await msg.edit(embed=embed)

        # Decide first attacker randomly; then alternate
        attacker_is_u1 = random.choice([True, False])

        # Battle loop
        while hp1 > 0 and hp2 > 0:
            attacker = user1 if attacker_is_u1 else user2
            defender = user2 if attacker_is_u1 else user1

            # Pick weighted attack
            move, dmg = _pick_attack()

            # Apply damage & clamp
            if attacker_is_u1:
                hp2 = max(0, hp2 - dmg)
            else:
                hp1 = max(0, hp1 - dmg)

            # 1) edit: update HP fields first
            embed.clear_fields()
            embed.add_field(name=f"{user1.name}", value=f"{EMOJI_HEALTH} {hp1}", inline=True)
            embed.add_field(name=f"{user2.name}", value=f"{EMOJI_HEALTH} {hp2}", inline=True)
            await msg.edit(embed=embed)

            # small delay before appending log line
            await asyncio.sleep(random.uniform(*FIELD_TO_LOG_DELAY_RANGE))

            # 2) edit: append combat log line (latest at bottom)
            line = (
                f"{EMOJI_BATTLE_LINE} __**{attacker.name}**__ {move} "
                f"__**{defender.name}**__ dealing **{dmg}** Damage"
            )
            desc_lines.append(line)
            desc_lines = _trim_desc(desc_lines)
            embed.description = "\n".join(desc_lines)
            await msg.edit(embed=embed)

            # End if someone is at 0
            if hp1 == 0 or hp2 == 0:
                break

            # Wait until next turn, then swap attacker
            await asyncio.sleep(random.uniform(*TURN_DELAY_RANGE))
            attacker_is_u1 = not attacker_is_u1

        # Winner announcement (title only changes)
        winner = user1 if hp2 == 0 else user2
        embed.title = f"{EMOJI_WINNER} {winner.name} Won!"
        # Keep the same image & final HP & log
        await msg.edit(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DeathBattle(bot))
