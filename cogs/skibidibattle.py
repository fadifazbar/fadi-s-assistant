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

BATTLE_SERVERS = [
    1422546075197374486,  # Server 1 ID
    1422546327731961973,  # Server 2 ID
    1422546580619137155,  # Server 3 ID
    1422546833388994711,  # Server 4 ID
    1422547085890420788,  # Server 5 ID
]

BATTLE_EMOJI = "<:battle:1422344657790177300>"
HP_EMOJI = "<:health:1422345046233059442>"

characters = {
    "Titan Speakerman 1.0": {
        "hp": 4500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
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
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
        ]
    },

    "Titan Cameraman 1.0": {
        "hp": 6500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
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
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
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
           "💥 Tv & Speaker Combo",
        ]
    },

    "Titan Tvman 2.0": {
        "hp": 50000,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "📺 Purple Light": {"damage": 1200, "rarity": 1},
            "📺 Red Light": {"damage": 1500, "rarity": 1},
            "🦶 Stomp": {"damage": 300, "rarity": 12},
            "👊 Punch": {"damage": 200, "rarity": 14},
            "🦵 Kick": {"damage": 350, "rarity": 12},
            "🤜 Crush": {"damage": 400, "rarity": 10},
            "✋ Slam": {"damage": 380, "rarity": 15},
            "🖐️ Slap": {"damage": 100, "rarity": 24},
            "🗡️ Sword Slash": {"damage": 950, "rarity": 8},
            "🦞 Shoulder Claws": {"damage": 750, "rarity": 14},
            "📺 Orange Light": {"damage": 1800, "rarity": 1},
            "💥 Core Blast": {"damage": 400, "rarity": 3},
            "☄️ Core Beam": {"damage": 2000, "rarity": 1},
            "🤕 Main Head Lasers": {"damage": 600, "rarity": 7},
            "📺 Shoulder TVs Rockets": {"damage": 480, "rarity": 8}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
        ]
    },

    "Titan SpeakerMan 2.0": {
        "hp": 13500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
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
           "💥 Tv & Speaker Combo",
        ]
    },

    "Titan Cinemaman": {
        "hp": 17400,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "📺 Red Light": {"damage": 700, "rarity": 2},
            "🎶 Speaker Blast": {"damage": 500, "rarity": 2},
            "💥 Tv & Speaker Combo": {"damage": 1500, "rarity": 1},
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
    },

    "G-Man 2.0": {
        "hp": 7500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👁️ Laser Eyes": {"damage": 300, "rarity": 6},
            "🚀 Mechanical Lasers": {"damage": 500, "rarity": 4},
            "💥 Laser Combo": {"damage": 2000, "rarity": 1},
            "👄 Bite": {"damage": 220, "rarity": 12},
            "🤕 HeadButt": {"damage": 210, "rarity": 14},
            "⏩ Dash": {"damage": 260, "rarity": 10}
        },
        "immunities": []
    },

    "G-Man 3.0": {
        "hp": 10000,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "🚀 Mechanical Lasers": {"damage": 1000, "rarity": 4},
            "👄 Bite": {"damage": 220, "rarity": 12},
            "🤕 HeadButt": {"damage": 210, "rarity": 14},
            "⏩ Dash": {"damage": 260, "rarity": 10}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
           "🎶 Speaker Blast",
           "🔊 Shock Wave",
           "📢 Massive Shockwave",
        ]
    },

    "Injured G-Man 3.0": {
        "hp": 6500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "🚀 Mechanical Lasers": {"damage": 400, "rarity": 4},
            "👄 Bite": {"damage": 220, "rarity": 12},
            "🤕 HeadButt": {"damage": 210, "rarity": 14},
            "⏩ Dash": {"damage": 260, "rarity": 10}
        },
        "immunities": []
    },

    "G-Man 4.0": {
        "hp": 24500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👁️ Laser Eyes": {"damage": 800, "rarity": 4},
            "🚀 Mechanical Lasers": {"damage": 1400, "rarity": 2},
            "💥 Laser Combo": {"damage": 4500, "rarity": 1},
            "🟡 Yellow Orb": {"damage": 750, "rarity": 5},
            "🟢 Green Orb": {"damage": 1000, "rarity": 3},
            "🟣 Purple Orb": {"damage": 1500, "rarity": 1},
            "👄 Bite": {"damage": 420, "rarity": 12},
            "🤕 HeadButt": {"damage": 410, "rarity": 14},
            "⏩ Dash": {"damage": 460, "rarity": 10},
            "🥽 Shield Dash": {"damage": 860, "rarity": 3}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
           "🎶 Speaker Blast",
           "🔊 Shock Wave",
           "📢 Massive Shockwave",
        ]
    },

    "Injured G-Man 4.0": {
        "hp": 14500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👁️ Laser Eyes": {"damage": 200, "rarity": 7},
            "🚀 Mechanical Lasers": {"damage": 400, "rarity": 6},
            "👄 Bite": {"damage": 420, "rarity": 12},
            "🤕 HeadButt": {"damage": 410, "rarity": 14},
            "⏩ Dash": {"damage": 460, "rarity": 10},
            "🥽 Shield Dash": {"damage": 860, "rarity": 3}
        },
        "immunities": [
           "💥 Tv & Speaker Combo",
           "🎶 Speaker Blast",
           "🔊 Shock Wave",
           "📢 Massive Shockwave",
        ]
    },

    "G-Man 5.0": {
        "hp": 75000,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👁️ Laser Eyes": {"damage": 2800, "rarity": 4},
            "🚀 Mechanical Lasers": {"damage": 4400, "rarity": 2},
            "💥 Laser Combo": {"damage": 10000, "rarity": 1},
            "🟡 Yellow Orb": {"damage": 750, "rarity": 5},
            "🟢 Green Orb": {"damage": 1000, "rarity": 3},
            "🟣 Purple Orb": {"damage": 1500, "rarity": 1},
            "👊 Punch": {"damage": 600, "rarity": 5},
            "💥 Combo Punch": {"damage": 1800, "rarity": 3},
            "🔪 Stab Punch": {"damage": 400, "rarity": 16},
            "👄 Bite": {"damage": 420, "rarity": 12},
            "🤕 HeadButt": {"damage": 410, "rarity": 14},
            "⏩ Dash": {"damage": 460, "rarity": 10},
            "🥽 Shield Dash": {"damage": 860, "rarity": 3}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
           "🎶 Speaker Blast",
           "🔊 Shock Wave",
           "📢 Massive Shockwave",
        ]
    },

    "Cameraman": {
        "hp": 100,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👊 Punch": {"damage": 10, "rarity": 14},
            "🦵 Kick": {"damage": 30, "rarity": 10},
            "🤜 Crush": {"damage": 57, "rarity": 6},
            "✋ Slam": {"damage": 76, "rarity": 4},
            "🖐️ Slap": {"damage": 46, "rarity": 8}
        },
        "immunities": []
    },

    "Large Cameraman": {
        "hp": 500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👊 Punch": {"damage": 30, "rarity": 14},
            "🦵 Kick": {"damage": 90, "rarity": 10},
            "🤜 Crush": {"damage": 100, "rarity": 6},
            "✋ Slam": {"damage": 150, "rarity": 4},
            "🖐️ Slap": {"damage": 80, "rarity": 8},
            "🥏 Grab & Throw": {"damage": 250, "rarity": 3}
        },
        "immunities": []
    },

    "Large Speakerman": {
        "hp": 1000,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👊 Punch": {"damage": 60, "rarity": 14},
            "🦵 Kick": {"damage": 150, "rarity": 10},
            "🤜 Crush": {"damage": 230, "rarity": 6},
            "✋ Slam": {"damage": 300, "rarity": 4},
            "🖐️ Slap": {"damage": 240, "rarity": 8},
            "🥏 Grab & Throw": {"damage": 500, "rarity": 3},
            "🎶 Speaker Blast": {"damage": 1000, "rarity": 1}

        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
]
    },

    "Strider Cameraman": {
        "hp": 750,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "☄️ Gun Shot": {"damage": 125, "rarity": 4},
            "💥 Crush": {"damage": 150, "rarity": 2},
            "🦶 Stomp": {"damage": 100, "rarity": 6}
        },
        "immunities": []
    },

    "Strider Speakerman": {
        "hp": 1250,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "📢 Massive Shockwave": {"damage": 3500, "rarity": 1},
            "💥 Crush": {"damage": 250, "rarity": 9},
            "🦶 Stomp": {"damage": 200, "rarity": 14}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
        ]
    },

    "Speakerman": {
        "hp": 200,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
        "attacks": {
            "👊 Punch": {"damage": 25, "rarity": 14},
            "🦵 Kick": {"damage": 45, "rarity": 10},
            "🤜 Crush": {"damage": 72, "rarity": 6},
            "✋ Slam": {"damage": 91, "rarity": 4},
            "🖐️ Slap": {"damage": 61, "rarity": 8},
            "🎶 Speaker Blast": {"damage": 500, "rarity": 3}
        },
        "immunities": [
           "📺 Red Light",
           "📺 Purple Light",
           "📺 Orange Light",
           "💥 Tv & Speaker Combo",
        ]
    },

    "G-Man 1.0": {
        "hp": 5500,
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
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
        "image": "https://wimg.rule34.xxx/thumbnails/1477/thumbnail_538b2893b5e73943cd4144d2685b3be9.jpg?13333162",
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
           "💥 Tv & Speaker Combo",
        ]
    }
}


class CharacterListView(discord.ui.View):
    def __init__(self, user, pages):
        super().__init__(timeout=180)
        self.user = user
        self.pages = pages  # list of (name, data)
        self.current_page = 0

    def make_page_embed(self, page_index):
        name, data = self.pages[page_index]
        embed = discord.Embed(
            title=f"{name} (Page {page_index+1}/{len(self.pages)})",
            description=f"{HP_EMOJI} {name}'w HP: {data['hp']}",
            color=discord.Color.orange()
        )
        # Add attacks field
        attacks_str = "\n".join([f"- {atk} ({info['damage']} dmg, rarity {info['rarity']})" for atk, info in data["attacks"].items()])
        embed.add_field(name="Attacks", value=attacks_str if attacks_str else "No attacks", inline=False)
        # Set image if exists
        if data.get("image"):
            embed.set_image(url=data["image"])
        return embed

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ This menu isn’t for you!", ephemeral=True)
        self.current_page = (self.current_page - 1) % len(self.pages)
        embed = self.make_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ This menu isn’t for you!", ephemeral=True)
        self.current_page = (self.current_page + 1) % len(self.pages)
        embed = self.make_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

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
active_emojis = {}       # emoji.id -> character_name
character_emojis = {}    # character_name -> emoji object
BATTLE_SERVERS = []      # list of guild IDs where emojis can be created


async def get_or_create_character_emoji(bot, character_name, image_url, servers):
    if character_name in character_emojis:
        return character_emojis[character_name]

    for guild in bot.guilds:
        if guild.id not in servers:
            continue
        for emoji in guild.emojis:
            if emoji.name.lower() == character_name.lower():
                character_emojis[character_name] = emoji
                active_emojis[emoji.id] = character_name
                return emoji

    for server_id in servers:
        guild = bot.get_guild(server_id)
        if guild is None:
            continue
        if len(guild.emojis) < guild.emoji_limit:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    img_bytes = await resp.read()
            try:
                emoji = await guild.create_custom_emoji(name=character_name, image=img_bytes)
                character_emojis[character_name] = emoji
                active_emojis[emoji.id] = character_name
                return emoji
            except discord.HTTPException:
                continue
    return None


async def release_character_emoji(character_name):
    for game in games.values():
        for char_data in game["characters"].values():
            if char_data["name"] == character_name:
                return

    emoji = character_emojis.get(character_name)
    if emoji:
        try:
            await emoji.delete()
        except:
            pass
        character_emojis.pop(character_name, None)
        active_emojis.pop(emoji.id, None)


# ---------------- BATTLE BUTTONS ----------------

class RetreatButton(discord.ui.Button):
    def __init__(self, game):
        super().__init__(label="🏳️ Retreat", style=discord.ButtonStyle.secondary)
        self.game = game
        self.retreat_votes = {}

    async def callback(self, interaction: discord.Interaction):
        if interaction.user not in self.game["players"]:
            return await interaction.response.send_message("❌ Only battle players can use this!", ephemeral=True)

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
        if all(self.votes.get(p.id) for p in self.game["players"]):
            channel = interaction.channel
            embed = discord.Embed(
                title="Skibidi Battle! 🚽⚔️",
                description="💨 Both characters have retreated and left the battlefield.\n\n# 🏆 Winner: TIE.",
                color=discord.Color.gold()
            )
            if self.game.get("message"):
                await self.game["message"].edit(embed=embed, view=None)
            games.pop(channel.id, None)
            for char_data in self.game["characters"].values():
                await release_character_emoji(char_data["name"])
            await interaction.followup.send("The battle has ended due to retreat.", ephemeral=True)
        else:
            await interaction.response.send_message("You voted ✅ Yes. Waiting for the other player...", ephemeral=True)


class RetreatNoButton(discord.ui.Button):
    def __init__(self, player, game, votes):
        super().__init__(label="⛔ No", style=discord.ButtonStyle.danger)
        self.player = player
        self.game = game
        self.votes = votes

    async def callback(self, interaction: discord.Interaction):
        self.votes[self.player.id] = False
        await interaction.response.send_message("You voted ❌ No. The battle will continue!", ephemeral=True)
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

        pool = []
        for atk_name, atk_data in char["attacks"].items():
            pool.extend([(atk_name, atk_data)] * atk_data["rarity"])
        chosen_attacks = random.sample(pool, min(3, len(pool)))

        button_style = discord.ButtonStyle.primary if attacker.id == game["players"][0].id else discord.ButtonStyle.danger

        for atk_name, atk_data in chosen_attacks:
            self.add_item(AttackButton(atk_name, atk_data, attacker, defender, game, button_style))

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

        immune = False
        immune_msg = None
        for imm in defender_char.get("immunities", []):
            if isinstance(imm, dict):
                if imm.get("character") == attacker_char["name"] and imm.get("attack") == self.atk_name:
                    immune = True
                    break
            elif isinstance(imm, str) and imm == self.atk_name:
                immune = True
                break

        dmg = 0 if immune else self.atk_data["damage"]
        if not immune:
            defender_char["hp"] = max(0, defender_char["hp"] - dmg)
        else:
            immune_msg = f"🛡️ {self.defender.mention}'s **{defender_char.get('name', 'Unknown')}** is immune to **{self.atk_name}**!"

        await asyncio.sleep(1.5)
        await update_battle_embed(interaction.client, interaction.channel, self.game, last_attack=(self.attacker, self.atk_name, dmg), immune_msg=immune_msg)

        if defender_char["hp"] <= 0:
            embed = discord.Embed(
                title="Skibidi Battle! 🚽⚔️",
                description=f"{immune_msg if immune_msg else f'**{self.attacker.mention}** used **{self.atk_name}** and dealt **{dmg} dmg** to **{defender_char.get('name', 'Unknown')}**!'}\n\n"
                            f"💥 {self.defender.mention}'s **{defender_char.get('name', 'Unknown')}** fainted!\n\n"
                            f"# 🏆 Winner: {self.attacker.mention}",
                color=discord.Color.gold()
            )
            await self.game["message"].edit(embed=embed, view=None)
            games.pop(interaction.channel.id, None)
            for char_data in self.game["characters"].values():
                await release_character_emoji(char_data["name"])
            return

        # Swap turn
        self.game["turn"] = self.defender.id
        p1, p2 = self.game["players"]
        turn_player = p1 if self.game["turn"] == p1.id else p2
        opponent = p2 if turn_player == p1 else p1
        view = AttackView(turn_player, opponent, self.game)
        await self.game["message"].edit(view=view)


async def update_battle_embed(bot, channel, game, last_attack=None, immune_msg=None):
    p1, p2 = game["players"]
    c1, c2 = game["characters"][p1.id], game["characters"][p2.id]

    attacker, atk_name, dmg = (last_attack if last_attack else (None, None, None))
    turn_player = p2 if attacker == p1 else p1 if attacker else p1
    opponent = p2 if turn_player == p1 else p1

    emoji1 = await get_or_create_character_emoji(bot, c1["name"], c1["image"], BATTLE_SERVERS)
    emoji2 = await get_or_create_character_emoji(bot, c2["name"], c2["image"], BATTLE_SERVERS)

    desc = f"{p1.mention} VS {p2.mention}\n\n"
    if immune_msg:
        desc += f"{immune_msg}\n\n"
    elif last_attack:
        desc += f"{emoji1 if attacker == p1 else emoji2} **{attacker.mention}** used **{atk_name}** and dealt **{dmg} dmg**!\n\n"
    desc += f"➡️ It's now **{turn_player.mention}**'s turn!"

    embed = discord.Embed(
        title="Skibidi Battle! 🚽⚔️",
        description=desc,
        color=discord.Color.red()
    )
    embed.add_field(name=f"{emoji1} {c1['name']} ({p1.name})", value=f"{c1['hp']} HP", inline=True)
    embed.add_field(name=f"{emoji2} {c2['name']} ({p2.name})", value=f"{c2['hp']} HP", inline=True)

    view = AttackView(turn_player, opponent, game)

    if "message" in game:
        await game["message"].edit(embed=embed, view=view)

# ================= Commands =================
class Skibidi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
