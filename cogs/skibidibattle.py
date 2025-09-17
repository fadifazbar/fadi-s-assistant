import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import random
import io

BATTLE_EMOJI = "<:battle_emoji:1408620699349946572>"
HP_EMOJI = "<:HP_V2:1408669354069065748>"

# ================= Characters =================
characters = {
    "Titan Speakerman 1.0": {
        "hp": 4500,
        "image": "https://cdn.discordapp.com/attachments/1404364969037922486/1417656455213088918/Titan_Speakerman1-0.png?ex=68cb46f5&is=68c9f575&hm=aecc159d6ffec1ba66ac5f48eda661c662ca5e23d5e650c411637ca38dacbc2b&",
        "attacks": {
            "💥 Cannon Blast": {"damage": 200, "rarity": 2},
            "🔊 Shock Wave": {"damage": 130, "rarity": 4},
            "🦶 Stomp": {"damage": 80, "rarity": 6},
            "👊 Punch": {"damage": 35, "rarity": 10},
            "🦵 Kick": {"damage": 57, "rarity": 8},
            "🤜 Crush": {"damage": 94, "rarity": 6},
            "✋ Slam": {"damage": 110, "rarity": 5},
            "🖐️ Slap": {"damage": 75, "rarity": 7}
        },
        "immunities": [
            "📺 Red Light",
        ]
    },

    "Titan Tvman 1.0": {
        "hp": 10415,
        "image": "https://cdn.discordapp.com/attachments/1404364969037922486/1417657393021587497/Titan_Tvman1-0.png?ex=68cb47d5&is=68c9f655&hm=deac76b2bb7cc1ac8c88a681bb24e5506abcb91bd9f7862490475631c31f4208&",
        "attacks": {
            "📺 Red Light": {"damage": 500, "rarity": 67},
            "🦶 Stomp": {"damage": 120, "rarity": 4},
            "👊 Punch": {"damage": 65, "rarity": 7},
            "🦵 Kick": {"damage": 97, "rarity": 5},
            "🤜 Crush": {"damage": 134, "rarity": 3},
            "✋ Slam": {"damage": 170, "rarity": 2},
            "🖐️ Slap": {"damage": 120, "rarity": 4},
            "🪝 Grapple Hook": {"damage": 59, "rarity": 8}
        },
        "immunities": []
    }
}

# ================= Helpers =================

def get_random_attacks(character):
    return random.sample(character["attacks"], 3)



async def url_to_file(url: str) -> io.BytesIO:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Image download failed: {url}")
            return io.BytesIO(await resp.read())

async def make_vs_image(url1: str, url2: str) -> io.BytesIO:
    """Combine 2 images side by side with a big VS"""
    img1_bytes = await url_to_file(url1)
    img2_bytes = await url_to_file(url2)

    img1 = Image.open(img1_bytes).convert("RGBA")
    img2 = Image.open(img2_bytes).convert("RGBA")

    height = 350
    img1 = img1.resize((int(img1.width * (height / img1.height)), height))
    img2 = img2.resize((int(img2.width * (height / img2.height)), height))

    spacing = 80
    total_width = img1.width + img2.width + spacing
    combined = Image.new("RGBA", (total_width, height), (0, 0, 0, 0))

    combined.paste(img1, (0, 0), img1)
    combined.paste(img2, (img1.width + spacing, 0), img2)

    draw = ImageDraw.Draw(combined)
    try:
        font = ImageFont.truetype("arialbd.ttf", 120)
    except:
        font = ImageFont.load_default()

    text = "VS"
# Draw VS text
    draw = ImageDraw.Draw(combined)
    try:
        font = ImageFont.truetype("arialbd.ttf", 120)
    except:
        font = ImageFont.load_default()

    text = "VS"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (total_width - text_width) // 2
    text_y = (height - text_height) // 2

    # Shadow + main text
    draw.text((text_x + 4, text_y + 4), text, font=font, fill="black")
    draw.text((text_x, text_y), text, font=font, fill="red")

    draw.text((text_x + 4, text_y + 4), text, font=font, fill="black")
    draw.text((text_x, text_y), text, font=font, fill="red")

    output = io.BytesIO()
    combined.save(output, format="PNG")
    output.seek(0)
    return output

# ================= Game Logic =================
games = {}  # channel_id -> game state


class AttackView(discord.ui.View):
    def __init__(self, attacker, defender, game):
        super().__init__(timeout=300)
        self.attacker = attacker
        self.defender = defender
        self.game = game

        char = game["characters"][attacker.id]

        # Build weighted pool based on rarity
        pool = []
        for atk_name, atk_data in char["attacks"].items():
            pool.extend([(atk_name, atk_data)] * atk_data["rarity"])

        # Pick up to 3 random weighted attacks
        chosen_attacks = random.sample(pool, min(3, len(pool)))

        # Pick button style depending on which player is attacking
        if attacker.id == game["players"][0].id:
            button_style = discord.ButtonStyle.primary  # Blue for Player 1
        else:
            button_style = discord.ButtonStyle.danger   # Red for Player 2

        for atk_name, atk_data in chosen_attacks:
            self.add_item(
                AttackButton(atk_name, atk_data, attacker, defender, game, button_style)
            )


class AttackButton(discord.ui.Button):
    def __init__(self, atk_name, atk_data, attacker, defender, game, button_style):
        super().__init__(label=f"{atk_name} ({atk_data['damage']} dmg)", style=button_style)
        self.atk_name = atk_name
        self.atk_data = atk_data
        self.attacker = attacker
        self.defender = defender
        self.game = game


async def callback(self, interaction: discord.Interaction):
    if interaction.user != self.attacker:
        return await interaction.response.send_message("❌ Not your turn!", ephemeral=True)

    attacker_char = self.game["characters"][self.attacker.id]
    defender_char = self.game["characters"][self.defender.id]

    # ================= Immunity check =================
    immune = False
    immune_msg = None
    for imm in defender_char.get("immunities", []):
        if isinstance(imm, dict):
            # dict format: {"character": "Titan Tvman 1.0", "attack": "📺 Red Light"}
            if imm.get("character") == attacker_char["name"] and imm.get("attack") == self.atk_name:
                immune = True
                break
        elif isinstance(imm, str):
            # text-only format: "📺 Red Light"
            if imm == self.atk_name:
                immune = True
                break

    if immune:
        dmg = 0
        immune_msg = f"🛡️ {self.defender.mention}'s **{defender_char.get('name', 'Unknown')}** is immune to **{self.atk_name}**!"
    else:
        dmg = self.atk_data["damage"]
        # Subtract HP from the defender (never the attacker)
        defender_char["hp"] = max(0, defender_char["hp"] - dmg)
        immune_msg = None  # No immune message; normal attack

    # ================== Response ==================
    await interaction.response.defer()
    await asyncio.sleep(1.5)

    channel = interaction.channel
    if defender_char["hp"] <= 0:
        embed = discord.Embed(
            title="Skibidi Battle! 🚽⚔️",
            description=f"{immune_msg if immune_msg else f'**{self.attacker.mention}** used **{self.atk_name}** and dealt **{dmg} dmg** to **{defender_char.get('name', 'Unknown')}**!'}\n\n"
                        f"💥 {self.defender.mention}'s **{defender_char.get('name', 'Unknown')}** fainted!\n\n"
                        f"🏆 Winner: {self.attacker.mention}",
            color=discord.Color.gold()
        )
        await self.game["message"].edit(embed=embed, view=None)
        games.pop(channel.id, None)
        return

    # Swap turns
    self.game["turn"] = self.defender.id
    await update_battle_embed(channel, self.game, last_attack=(self.attacker, self.atk_name, dmg), immune_msg=immune_msg)

async def update_battle_embed(channel, game, last_attack=None, immune_msg=None):
    p1, p2 = game["players"]
    c1, c2 = game["characters"][p1.id], game["characters"][p2.id]

    # Determine whose turn it is
    turn_player = p1 if game["turn"] == p1.id else p2
    opponent = p2 if turn_player == p1 else p1

    # Build description
    desc = f"{p1.mention} VS {p2.mention}\n\n"

    if immune_msg:  # If the defender is immune, show this instead
        desc += f"{immune_msg}\n\n"
    elif last_attack:
        attacker, atk_name, dmg = last_attack
        desc += f"{BATTLE_EMOJI} **{attacker.mention}** used **{atk_name}** and dealt **{dmg} dmg**!\n\n"

    desc += f"➡️ It's now **{turn_player.mention}**'s turn!"

    # Create embed
    embed = discord.Embed(
        title="Skibidi Battle! 🚽⚔️",
        description=desc,
        color=discord.Color.red()
    )
    embed.add_field(
        name=f"{c1['name']} ({p1.name})",
        value=f"{HP_EMOJI} {c1['hp']} HP",
        inline=True
    )
    embed.add_field(
        name=f"{c2['name']} ({p2.name})",
        value=f"{HP_EMOJI} {c2['hp']} HP",
        inline=True
    )

        # Build attack buttons for the current turn
        view = AttackView(turn_player, opponent, game)

        # Send or edit message
        if "message" not in game:
            vs_image = await make_vs_image(c1["image"], c2["image"])
            file = discord.File(vs_image, filename="vs.png")
            msg = await channel.send(file=file, embed=embed, view=view)
            game["message"] = msg
        else:
            await game["message"].edit(embed=embed, view=view)

# ================= Commands =================
class Skibidi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="skibidi", aliases=["sk", "battle", "toilet"])
    async def skibidi_prefix(self, ctx, opponent: discord.Member):
        await self.start_battle(ctx.author, opponent, ctx.channel)

    @app_commands.command(name="skibidi", description="Challenge someone to a Skibidi battle")
    async def skibidi_slash(self, interaction: discord.Interaction, target: discord.Member):
        await self.start_battle(interaction.user, target, interaction.channel, interaction=interaction)

    async def start_battle(self, player1, player2, channel, interaction=None):
        if channel.id in games:
            msg = "⚠️ A battle is already in progress in this channel!"
            if interaction:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await channel.send(msg)
            return

        confirm_embed = discord.Embed(
            title="Skibidi Battle! 🚽⚔️",
            description=f"{player1.mention} has challenged {player2.mention}!\n\nDo you accept?",
            color=discord.Color.blue()
        )

        view = ConfirmView(player1, player2, channel)

        if interaction:
            await interaction.response.send_message(
                content=f"||{player1.mention} {player2.mention}||",
                embed=confirm_embed,
                view=view
            )
        else:
            await channel.send(
                content=f"||{player1.mention} {player2.mention}||",
                embed=confirm_embed,
                view=view
            )

class ConfirmView(discord.ui.View):
    def __init__(self, player1, player2, channel):
        super().__init__(timeout=300)
        self.player1 = player1
        self.player2 = player2
        self.channel = channel

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.player2:
            return await interaction.response.send_message("❌ Only the challenged player can accept!", ephemeral=True)

        p1_char = random.choice(list(characters.keys()))
        p2_char = random.choice(list(characters.keys()))
        while p2_char == p1_char:
            p2_char = random.choice(list(characters.keys()))

        games[self.channel.id] = {
            "players": [self.player1, self.player2],
            "characters": {
                self.player1.id: {**characters[p1_char], "name": p1_char, "hp": characters[p1_char]["hp"]},
                self.player2.id: {**characters[p2_char], "name": p2_char, "hp": characters[p2_char]["hp"]},
            },
            "turn": self.player1.id
        }

        await interaction.response.edit_message(content="✅ Battle accepted!", embed=None, view=None)
        await update_battle_embed(self.channel, games[self.channel.id])

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.player2:
            return await interaction.response.send_message("❌ Only the challenged player can decline!", ephemeral=True)

        await interaction.response.edit_message(content=f"{self.player2.mention} declined the challenge.", embed=None, view=None)

    async def on_timeout(self):
        await self.message.edit(content="⌛ Challenge expired.", view=None)

# ============ SETUP ============
async def setup(bot):
    await bot.add_cog(Skibidi(bot))