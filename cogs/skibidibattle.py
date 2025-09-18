import discord
from discord.ext import commands
from discord import app_commands, Interaction
import random
import asyncio
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import random
import io
import difflib
import json
import os

DATA_FILE = "data/player_data.json"

# Ensure folder
os.makedirs("data", exist_ok=True)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(player_data, f, indent=2)

player_data = load_data()


BATTLE_EMOJI = "<:battle_emoji:1408620699349946572>"
HP_EMOJI = "<:HP_V2:1408669354069065748>"

characters = {
    "Titan Speakerman 1.0": {
        "hp": 4500,
        "price": 2500,
        "image": "https://i.postimg.cc/PrzvSrd7/Titan-Speakerman1-0.png",
        "attacks": {
            "💥 Cannon Blast": {"damage": 400, "rarity": 6},
            "🔊 Shock Wave": {"damage": 200, "rarity": 10},
            "🦶 Stomp": {"damage": 150, "rarity": 12},
            "👊 Punch": {"damage": 60, "rarity": 18},
            "🦵 Kick": {"damage": 90, "rarity": 16},
            "🤜 Crush": {"damage": 180, "rarity": 10},
            "✋ Slam": {"damage": 250, "rarity": 8},
            "🖐️ Slap": {"damage": 80, "rarity": 14}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
        ]
    },

    "Titan Cameraman 1.0": {
        "hp": 6500,
        "price": 4500,
        "image": "https://i.postimg.cc/PqcCCCMC/Titan-Cameraman1-0.png",
        "attacks": {
            "💫 Core Beam": {"damage": 300, "rarity": 2},
            "💥 Ground Smash": {"damage": 200, "rarity": 6},
            "🦵 Kick": {"damage": 170, "rarity": 4},
            "🥏 Grab & Throw": {"damage": 260, "rarity": 4},
            "🦶 Stomp": {"damage": 90, "rarity": 16},
            "👊 Punch": {"damage": 60, "rarity": 14}
        },
        "immunities": []
    },

    "Titan Cameraman 2.0": {
        "hp":20000,
        "price": 18000,
        "image": "https://i.postimg.cc/SRmkR4HX/Titan-Cameraman2-0.png",
        "attacks": {
            "💥 Blaster": {"damage": 380, "rarity": 7},
            "🦵 Kick": {"damage": 200, "rarity": 8},
            "🥏 Grab & Throw": {"damage": 360, "rarity": 4},
            "🦶 Stomp": {"damage": 150, "rarity": 14},
            "👊 Punch": {"damage": 120, "rarity": 16},
            "🔥 Core Fire": {"damage": 800, "rarity": 1},
            "⚒️ Hammer Smash": {"damage": 560, "rarity": 3},
            "👏 Double Hand Slap": {"damage": 180, "rarity": 5},
            "🤕 Head Crush": {"damage": 200, "rarity": 2},
            "🤗 Tackle": {"damage": 240, "rarity": 4},
            "🔫 Shoulder Rockets": {"damage": 270, "rarity": 3},
            "🧲 Magnet Hand": {"damage": 320, "rarity": 2},
            "🥊 Claw Hand Punch": {"damage": 320, "rarity": 2}

        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
        ]
    },

    "Titan Tvman 2.0": {
        "hp": 30000,
        "price": 27000,
        "image": "https://i.postimg.cc/X7H4jTLJ/Titan-Tvman2-0.png",
        "attacks": {
            "📺 Purple Light": {"damage": 1200, "rarity": 1},
            "📺 Red Light": {"damage": 1500, "rarity": 1},
            "🦶 Stomp": {"damage": 450, "rarity": 8},
            "👊 Punch": {"damage": 400, "rarity": 14},
            "🦵 Kick": {"damage": 500, "rarity": 10},
            "🤜 Crush": {"damage": 600, "rarity": 6},
            "✋ Slam": {"damage": 580, "rarity": 6},
            "🖐️ Slap": {"damage": 300, "rarity": 8},
            "🗡️ Sword Slash": {"damage": 750, "rarity": 8},
            "🦞 Shoulder Claws": {"damage": 250, "rarity": 14},
            "📺 Orange Light": {"damage": 1800, "rarity": 1},
            "💥 Core Blast": {"damage": 400, "rarity": 3},
            "☄️ Core Beam": {"damage": 2000, "rarity": 1},
            "🤕 Main Head Lasers": {"damage": 200, "rarity": 14},
            "📺 Shoulder TVs Rockets": {"damage": 180, "rarity": 26}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
        ]
    },

    "Titan SpeakerMan 2.0": {
        "hp": 13500,
        "price": 10500,
        "image": "https://i.postimg.cc/2yTmBJf0/Titan-Speakerman2-0.png",
        "attacks": {
            "🛰️ Blaster Shot": {"damage": 220, "rarity": 5},
            "🔊 Shock Wave": {"damage": 350, "rarity": 4},
            "🦶 Stomp": {"damage": 150, "rarity": 12},
            "👊 Punch": {"damage": 200, "rarity": 20},
            "🦵 Kick": {"damage": 175, "rarity": 16},
            "🤜 Crush": {"damage": 210, "rarity": 12},
            "✋ Slam": {"damage": 200, "rarity": 10},
            "🖐️ Slap": {"damage": 120, "rarity": 14},
            "‼️ Double Blasts": {"damage": 380, "rarity": 9},
            "💡 Core Laser": {"damage": 190, "rarity": 8},
            "🔪 Stab": {"damage": 100, "rarity": 28},
            "📢 Massive Shockwave": {"damage": 850, "rarity": 1}
        },
        "immunities": [
           "🔊 Shock Wave",
           "📢 Massive Shockwave",
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
        ]
    },

    "G-Man 1.0": {
        "hp": 5500,
        "image": "https://i.postimg.cc/sgLjctG8/G-Man-Toilet1-0.png",
        "attacks": {
            "👁️ Laser Eyes": {"damage": 300, "rarity": 6},
            "👄 Bite": {"damage": 220, "rarity": 12},
            "🤕 HeadButt": {"damage": 210, "rarity": 14},
            "⏩ Dash": {"damage": 260, "rarity": 10}
        },
        "immunities": [
           "🧲 Magnet Hand",
        ]
    },


    "Titan Tvman 1.0": {
        "hp": 14500,
        "price": 7500,
        "image": "https://i.postimg.cc/vTyHnfxZ/Titan-Tvman1-0.png",
        "attacks": {
            "📺 Red Light": {"damage": 700, "rarity": 2},
            "🦶 Stomp": {"damage": 180, "rarity": 8},
            "👊 Punch": {"damage": 100, "rarity": 14},
            "🦵 Kick": {"damage": 140, "rarity": 10},
            "🤜 Crush": {"damage": 200, "rarity": 6},
            "✋ Slam": {"damage": 250, "rarity": 4},
            "🖐️ Slap": {"damage": 160, "rarity": 8},
            "🪝 Grapple Hook": {"damage": 120, "rarity": 16},
            "🦞 Shoulder Claws": {"damage": 150, "rarity": 14}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
        ]
    }
}



class CharacterListView(discord.ui.View):
    def __init__(self, user, pages, mode="shop"):
        """
        mode: "shop" = show buy button
              "inv"  = show equip button
        """
        super().__init__(timeout=180)
        self.user = user
        self.pages = pages  # list of (name, data)
        self.current_page = 0
        self.mode = mode  # shop or inv

        # Set button label and style dynamically
        if self.mode == "shop":
            button_label = "🛒 Buy"
            button_style = discord.ButtonStyle.green
        elif self.mode == "inv":
            button_label = "⚔️ Equip"
            button_style = discord.ButtonStyle.primary
        else:
            button_label = "🛒 Buy / ⚔️ Equip"
            button_style = discord.ButtonStyle.green

        # Replace the static button with dynamic one
        self.buy_or_equip_button = discord.ui.Button(label=button_label, style=button_style)
        self.buy_or_equip_button.callback = self.buy_or_equip
        self.add_item(self.buy_or_equip_button)

    def make_page_embed(self, page_index):
        name, data = self.pages[page_index]
        embed = discord.Embed(
            title=f"{name} (Page {page_index+1}/{len(self.pages)})",
            color=discord.Color.orange()
        )
        # Show different info based on mode
        if self.mode == "shop":
            embed.description = f"💰 Price: {data.get('price', 0)} Coins"
        elif self.mode == "inv":
            hp = data.get("hp", "Unknown")
            attacks_str = "\n".join([f"- {atk} ({info['damage']} dmg, rarity {info['rarity']})" for atk, info in data["attacks"].items()])
            embed.description = f"{HP_EMOJI} {name}'s HP: {hp}\n\nAttacks:\n{attacks_str}"
            # Show equipped
            user_chars = player_data.get(self.user.id, {})
            if user_chars.get("equipped") == name:
                embed.set_footer(text="Equipped ✅")
        # Image
        if data.get("image"):
            embed.set_image(url=data["image"])
        return embed

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ This menu isn’t for you!", ephemeral=True)
        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.make_page_embed(self.current_page), view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ This menu isn’t for you!", ephemeral=True)
        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.make_page_embed(self.current_page), view=self)

    async def buy_or_equip(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ This menu isn’t for you!", ephemeral=True)

        name, data = self.pages[self.current_page]
        user_chars = player_data.setdefault(self.user.id, {"coins": 0, "owned": [], "equipped": None})

        if self.mode == "shop":
            price = data.get("price", 0)
            if name in user_chars["owned"]:
                return await interaction.response.send_message("✅ You already own this character!", ephemeral=True)
            if user_chars["coins"] < price:
                return await interaction.response.send_message("❌ Not enough coins!", ephemeral=True)
            user_chars["coins"] -= price
            user_chars["owned"].append(name)
            save_data()
            await interaction.response.send_message(f"💰 You bought **{name}** for {price} coins!", ephemeral=True)

        elif self.mode == "inv":
            if name not in user_chars["owned"]:
                return await interaction.response.send_message("❌ You do not own this character!", ephemeral=True)
            user_chars["equipped"] = name
            save_data()
            await interaction.response.send_message(f"⚔️ You equipped **{name}**!", ephemeral=True)

        # Update embed after buy/equip
        await interaction.message.edit(embed=self.make_page_embed(self.current_page), view=self)




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
    text_x = (total_width - text_width) // 50
    text_y = (height - text_height) // 50

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


class RetreatButton(discord.ui.Button):
    def __init__(self, game):
        super().__init__(label="🏳️ Retreat", style=discord.ButtonStyle.secondary)
        self.game = game
        self.retreat_votes = {}  # Track votes: {player_id: True/False}

    async def callback(self, interaction: discord.Interaction):
        # Only battle players can press
        if interaction.user not in self.game["players"]:
            return await interaction.response.send_message("❌ Only battle players can use this!", ephemeral=True)

        # Send ephemeral confirmation embed
        confirm_embed = discord.Embed(
            title="🏳️ Retreat Confirmation",
            description="Do you want to stop the game?",
            color=discord.Color.gold()
        )
        view = RetreatConfirmView(interaction.user, self.game, self.retreat_votes)
        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)


class RetreatConfirmView(discord.ui.View):
    def __init__(self, player, game, votes):
        super().__init__(timeout=7)
        self.game = game
        self.player = player
        self.votes = votes
        self.add_item(RetreatYesButton(player, game, votes))
        self.add_item(RetreatNoButton(player, game, votes))

    async def on_timeout(self):
        # Disable buttons on timeout
        for child in self.children:
            child.disabled = True


class RetreatYesButton(discord.ui.Button):
    def __init__(self, player, game, votes):
        super().__init__(label="✅ Yes", style=discord.ButtonStyle.success)
        self.player = player
        self.game = game
        self.votes = votes

    async def callback(self, interaction: discord.Interaction):
        self.votes[self.player.id] = True

        # If both players voted yes
        if all(self.votes.get(p.id) for p in self.game["players"]):
            channel = interaction.channel
            other_player = [p for p in self.game["players"] if p != self.player][0]
            retreated_char = self.game["characters"][self.player.id]["name"]
            winner_char = self.game["characters"][other_player.id]["name"]

            # Update main battle embed
            embed = discord.Embed(
                title="Skibidi Battle! 🚽⚔️",
                description=f"💨 Both characters has retreated and left the battlefield.\n\n"
                            f"# 🏆 Winner: TIE.",
                color=discord.Color.gold()
            )
            await self.game["message"].edit(embed=embed, view=None)
            # Remove game from active games
            games.pop(channel.id, None)

            await interaction.followup.send("The battle has ended due to retreat.", ephemeral=True)
        else:
            await interaction.response.send_message("You voted ✅ Yes to retreat. Waiting for the other player...", ephemeral=True)


class RetreatNoButton(discord.ui.Button):
    def __init__(self, player, game, votes):
        super().__init__(label="⛔ No", style=discord.ButtonStyle.danger)
        self.player = player
        self.game = game
        self.votes = votes

    async def callback(self, interaction: discord.Interaction):
        self.votes[self.player.id] = False
        await interaction.response.send_message("You voted ❌ No. The battle will continue!", ephemeral=True)
        # Clear confirmation message after 7 seconds
        await asyncio.sleep(7)
        try:
            await interaction.message.delete()
        except:
            pass


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

        # Add attack buttons
        for atk_name, atk_data in chosen_attacks:
            self.add_item(
                AttackButton(atk_name, atk_data, attacker, defender, game, button_style)
            )

        # Add retreat button at the end
        self.add_item(RetreatButton(game))

class AttackButton(discord.ui.Button):
    def __init__(self, atk_name, atk_data, attacker, defender, game, button_style):
        super().__init__(label=f"{atk_name} ({atk_data['damage']} dmg)", style=button_style)
        self.atk_name = atk_name
        self.atk_data = atk_data
        self.attacker = attacker
        self.defender = defender
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if interaction.user != self.attacker:
            return await interaction.followup.send("❌ Not your turn!", ephemeral=True)

        attacker_char = self.game["characters"][self.attacker.id]
        defender_char = self.game["characters"][self.defender.id]

        # Immunity check
        immune = False
        immune_msg = None
        for imm in defender_char.get("immunities", []):
            if isinstance(imm, dict):
                if imm.get("character") == attacker_char["name"] and imm.get("attack") == self.atk_name:
                    immune = True
                    break
            elif isinstance(imm, str):
                if imm == self.atk_name:
                    immune = True
                    break

        if immune:
            dmg = 0
            immune_msg = f"🛡️ {self.defender.mention}'s **{defender_char.get('name', 'Unknown')}** is immune to **{self.atk_name}**!"
        else:
            dmg = self.atk_data["damage"]
            defender_char["hp"] = max(0, defender_char["hp"] - dmg)
            immune_msg = None

        await asyncio.sleep(1.5)
        await update_battle_embed(interaction.channel, self.game, last_attack=(self.attacker, self.atk_name, dmg), immune_msg=immune_msg)

        # Handle faint
        if defender_char["hp"] <= 0:
            winner = self.attacker
            loser = self.defender

            # Ensure both players exist in player_data
            player_data.setdefault(winner.id, {"coins": 0, "owned": [], "equipped": None})
            player_data.setdefault(loser.id, {"coins": 0, "owned": [], "equipped": None})

            # Update coins
            player_data[winner.id]["coins"] += 500
            player_data[loser.id]["coins"] += 100

            # Persist changes
            save_data()

            embed = discord.Embed(
                title="Skibidi Battle! 🚽⚔️",
                description=f"{immune_msg if immune_msg else f'**{winner.mention}** used **{self.atk_name}** and dealt **{dmg} dmg** to **{defender_char.get('name', 'Unknown')}**!'}\n\n"
                            f"💥 {loser.mention}'s **{defender_char.get('name', 'Unknown')}** fainted!\n\n"
                            f"# 🏆 Winner: {winner.mention}\n"
                            f"💰 {winner.mention} earned 500 coins!\n"
                            f"💰 {loser.mention} earned 100 coins for participating!",
                color=discord.Color.gold()
            )
            await self.game["message"].edit(embed=embed, view=None)
            games.pop(interaction.channel.id, None)
            return

        # Swap turns
        self.game["turn"] = self.defender.id
        p1, p2 = self.game["players"]
        turn_player = p1 if self.game["turn"] == p1.id else p2
        opponent = p2 if turn_player == p1 else p1
        view = AttackView(turn_player, opponent, self.game)
        await self.game["message"].edit(view=view)



async def update_battle_embed(channel, game, last_attack=None, immune_msg=None):
    p1, p2 = game["players"]
    c1, c2 = game["characters"][p1.id], game["characters"][p2.id]

    # Determine attacker and opponent
    if last_attack:
        attacker, atk_name, dmg = last_attack
        opponent = p2 if attacker == p1 else p1
        turn_player = opponent  # next turn is opponent
    else:
        turn_player = p1 if game["turn"] == p1.id else p2
        opponent = p2 if turn_player == p1 else p1

    # Build description
    desc = f"{p1.mention} VS {p2.mention}\n\n"
    if immune_msg:
        desc += f"{immune_msg}\n\n"
    elif last_attack:
        desc += f"{BATTLE_EMOJI} **{attacker.mention}** used **{atk_name}** and dealt **{dmg} dmg**!\n\n"
    desc += f"➡️ It's now **{turn_player.mention}**'s turn!"

    # Create embed
    embed = discord.Embed(
        title="Skibidi Battle! 🚽⚔️",
        description=desc,
        color=discord.Color.red()
    )

    # Add HP fields
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

    # Send new message if first time, else edit existing
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

    # ===== PREFIX COMMAND =====
    @commands.command(name="coins", aliases=["cash", "money"])
    async def coins_prefix(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        user_data = player_data.get(user_id, {"coins": 0})
        coins = user_data.get("coins", 0)
        if target == ctx.author:
            await ctx.send(f"💰 You have **{coins} coins**.")
        else:
            await ctx.send(f"💰 {target.display_name} has **{coins} coins**.")

    # ===== SLASH COMMAND =====
    @app_commands.command(name="coins", description="Check your or someone else's coins")
    @app_commands.describe(member="Optional: User to check coins of")
    async def coins_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        user_id = str(target.id)
        user_data = player_data.get(user_id, {"coins": 0})
        coins = user_data.get("coins", 0)
        if target == interaction.user:
            await interaction.response.send_message(f"💰 You have **{coins} coins**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"💰 {target.display_name} has **{coins} coins**.", ephemeral=False)

    # ===== Shop =====
    @commands.command(name="shop")
    async def shop_prefix(self, ctx, *, search: str = None):
        pages = [(name, data) for name, data in characters.items()]
        if search:
            matches = [item for item in pages if search.lower() in item[0].lower()]
            if matches:
                pages = matches
            else:
                return await ctx.send("❌ No character found matching that name.")
        view = CharacterListView(ctx.author, pages, mode="shop")
        embed = view.make_page_embed(0)
        view.message = await ctx.send(embed=embed, view=view)

    @app_commands.command(name="shop", description="Browse characters in the shop")
    async def shop_slash(self, interaction: discord.Interaction, search: str = None):
        pages = [(name, data) for name, data in characters.items()]
        if search:
            matches = [item for item in pages if search.lower() in item[0].lower()]
            if matches:
                pages = matches
            else:
                return await interaction.response.send_message("❌ No character found matching that name.", ephemeral=True)
        view = CharacterListView(interaction.user, pages, mode="shop")
        embed = view.make_page_embed(0)
        await interaction.response.send_message(embed=embed, view=view)

    # ===== Inventory =====
    @commands.command(name="inventory", aliases=["inv", "backpack"])
    async def inventory_prefix(self, ctx):
        user_chars = player_data.get(ctx.author.id, {"coins": 0, "owned": [], "equipped": None})
        pages = [(name, characters[name]) for name in user_chars["owned"]]
        if not pages:
            return await ctx.send("❌ You don't own any characters yet.")
        view = CharacterListView(ctx.author, pages, mode="inv")
        embed = view.make_page_embed(0)
        view.message = await ctx.send(embed=embed, view=view)

    @app_commands.command(name="inventory", description="Show your owned characters and equip")
    async def inventory_slash(self, interaction: discord.Interaction):
        user_chars = player_data.get(interaction.user.id, {"coins": 0, "owned": [], "equipped": None})
        pages = [(name, characters[name]) for name in user_chars["owned"]]
        if not pages:
            return await interaction.response.send_message("❌ You don't own any characters yet.", ephemeral=True)
        view = CharacterListView(interaction.user, pages, mode="inv")
        embed = view.make_page_embed(0)
        await interaction.response.send_message(embed=embed, view=view)

# ========== PREFIX ==========
    @commands.command(name="skibidilist")
    async def skibidi_list_prefix(self, ctx, *, search: str = None):
        pages = [(name, data) for name, data in characters.items()]

        if search:
            name, data = self.find_character(search)
            if name:
                pages = [(name, data)]
            else:
                await ctx.send("❌ No character found matching that name.")
                return

        view = CharacterListView(ctx.author, pages)
        embed = view.make_page_embed(0)
        view.message = await ctx.send(embed=embed, view=view)

    # ========== SLASH ==========
    @app_commands.command(name="skibidilist", description="List all available characters")
    @app_commands.describe(character="Optional character name to search")
    async def skibidi_list_slash(self, interaction: discord.Interaction, character: str = None):
        pages = [(name, data) for name, data in characters.items()]

        if character:
            name, data = self.find_character(character)
            if name:
                pages = [(name, data)]
            else:
                await interaction.response.send_message(
                    "❌ No character found matching that name.", ephemeral=True
                )
                return

        view = CharacterListView(interaction.user, pages)
        embed = view.make_page_embed(0)
        view.message = await interaction.response.send_message(embed=embed, view=view)

    # ========== AUTOCOMPLETE ==========
    @skibidi_list_slash.autocomplete("character")
    async def character_autocomplete(self, interaction: discord.Interaction, current: str):
        if not current:
            return [app_commands.Choice(name=name, value=name) for name in list(characters.keys())[:20]]

        matches = difflib.get_close_matches(current, characters.keys(), n=20, cutoff=0.2)
        return [app_commands.Choice(name=match, value=match) for match in matches]

    # ========== HELPER ==========
    def find_character(self, query: str):
        """Find the closest character name to the query using fuzzy matching."""
        if query in characters:
            return query, characters[query]

        matches = difflib.get_close_matches(query, characters.keys(), n=1, cutoff=0.2)
        if matches:
            best_match = matches[0]
            return best_match, characters[best_match]

        return None, None

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
    def __init__(self, player1, player2, channel, bot):
        super().__init__(timeout=300)
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.bot = bot

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.player2:
            return await interaction.response.send_message(
                "❌ Only the challenged player can accept!", ephemeral=True
            )

        # ---------------- Get equipped characters ----------------
        # Load player data (coins, inventory, equipped)
        player1_data = await get_player_data(self.player1.id)
        player2_data = await get_player_data(self.player2.id)

        if not player1_data.get("equipped") or not player2_data.get("equipped"):
            return await interaction.response.send_message(
                "❌ Both players must have an equipped character to start the battle!", ephemeral=True
            )

        p1_char_name = player1_data["equipped"]
        p2_char_name = player2_data["equipped"]

        games[self.channel.id] = {
            "players": [self.player1, self.player2],
            "characters": {
                self.player1.id: {**characters[p1_char_name], "name": p1_char_name, "hp": characters[p1_char_name]["hp"]},
                self.player2.id: {**characters[p2_char_name], "name": p2_char_name, "hp": characters[p2_char_name]["hp"]},
            },
            "turn": self.player1.id
        }

        await interaction.response.edit_message(content="✅ Battle accepted!", embed=None, view=None)
        await update_battle_embed(self.channel, games[self.channel.id])

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.player2:
            return await interaction.response.send_message(
                "❌ Only the challenged player can decline!", ephemeral=True
            )

        await interaction.response.edit_message(
            content=f"{self.player2.mention} declined the challenge.", embed=None, view=None
        )

    async def on_timeout(self):
        if hasattr(self, "message"):
            await self.message.edit(content="⌛ Challenge expired.", view=None)


# ---------------- Updated start_battle ----------------
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

    view = ConfirmView(player1, player2, channel, self.bot)

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


# ---------------- Helper to fetch player data ----------------
async def get_player_data(user_id):
    """Load a player's data (inventory, coins, equipped) from DB or local storage."""
    # Replace with your data system (Railway, JSON, etc.)
    # Example structure:
    # {
    #   "coins": 500,
    #   "owned": ["Titan Tvman 1.0", "TiTa CaMeRA2"],
    #   "equipped": "Titan Tvman 1.0"
    # }
    # If no data exists, return defaults
    try:
        data = await load_user_data(user_id)
        return {
            "coins": data.get("coins", 0),
            "owned": data.get("owned", []),
            "equipped": data.get("equipped", None)
        }
    except:
        return {"coins": 0, "owned": [], "equipped": None}


# ============ SETUP ============
async def setup(bot):
    await bot.add_cog(Skibidi(bot))
