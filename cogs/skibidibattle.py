import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import io

# ================= Characters =================
characters = {
    "Titan Speakerman 1.0": {
        "hp": 120,
        "image": "https://cdn.discordapp.com/attachments/1404364969037922486/1417656455213088918/Titan_Speakerman1-0.png?ex=68cb46f5&is=68c9f575&hm=aecc159d6ffec1ba66ac5f48eda661c662ca5e23d5e650c411637ca38dacbc2b&",
        "attacks": {
            "Bass Blast": 25,
            "Mic Smash": 30,
            "Sonic Wave": 20,
            "Quadruple Blast": 100
        }
    },
    "Titan Cameraman 1.0": {
        "hp": 110,
        "image": "https://cdn.discordapp.com/attachments/1404364969037922486/1417656456248954900/Titan_Cameraman1-0.png?ex=68cb46f5&is=68c9f575&hm=f90ca1f459498786168c7c52ee64495ae5d619d0d95aa108821cd35561a158eb&",
        "attacks": {
            "Flash Shot": 22,
            "Tripod Slam": 28,
            "Zoom Strike": 26,
            "Heavy Atom": 34
        }
    },
    "G-Man 1.0": {
        "hp": 130,
        "image": "https://cdn.discordapp.com/attachments/1404364969037922486/1417656457330954353/G-Man_Toilet1-0.png?ex=68cb46f6&is=68c9f576&hm=a24e890e4a7b8af877041d11b7a559f08c52b05645985d6d26fd7926ec92f0d6&",
        "attacks": {
            "Fist Smash": 24,
            "Power Punch": 32,
            "Ground Slam": 27,
            "Laser Eye": 30
        }
    },
    "Titan Tvman 1.0": {
        "hp": 115,
        "image": "https://cdn.discordapp.com/attachments/1404364969037922486/1417657393021587497/Titan_Tvman1-0.png?ex=68cb47d5&is=68c9f655&hm=deac76b2bb7cc1ac8c88a681bb24e5506abcb91bd9f7862490475631c31f4208&",
        "attacks": {
            "Static Shock": 20,
            "Channel Crush": 29,
            "Screen Slam": 26,
            "Red Light": 47
        }
    }
}

# ================= Helpers =================
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
    text_width, text_height = draw.textsize(text, font=font)
    text_x = (total_width - text_width) // 2
    text_y = (height - text_height) // 2

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
        for atk_name, dmg in char["attacks"].items():
            self.add_item(AttackButton(atk_name, dmg, attacker, defender, game))

    async def on_timeout(self):
        if "message" in self.game:
            await self.game["message"].edit(content="⏰ Battle ended due to inactivity.", view=None)

class AttackButton(discord.ui.Button):
    def __init__(self, atk_name, dmg, attacker, defender, game):
        super().__init__(label=f"{atk_name} ({dmg} dmg)", style=discord.ButtonStyle.red)
        self.atk_name = atk_name
        self.dmg = dmg
        self.attacker = attacker
        self.defender = defender
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.attacker:
            return await interaction.response.send_message("❌ Not your turn!", ephemeral=True)

        defender_char = self.game["characters"][self.defender.id]
        defender_char["hp"] -= self.dmg

        await interaction.response.defer()
        await asyncio.sleep(1.5)  # small delay for dramatic effect

        channel = interaction.channel
        if defender_char["hp"] <= 0:
            embed = discord.Embed(
                title="Skibidi Battle! 🚽⚔️",
                description=f"**{self.attacker.mention}** used **{self.atk_name}**!\n\n💥 {self.defender.mention}'s {defender_char['name']} fainted!\n\n🏆 Winner: {self.attacker.mention}",
                color=discord.Color.gold()
            )
            await self.game["message"].edit(embed=embed, view=None)
            games.pop(channel.id, None)
            return

        # Swap turns
        self.game["turn"] = self.defender.id
        await update_battle_embed(channel, self.game, last_attack=(self.attacker, self.atk_name, self.dmg))

async def update_battle_embed(channel, game, last_attack=None):
    p1, p2 = game["players"]
    c1, c2 = game["characters"][p1.id], game["characters"][p2.id]

    desc = f"{p1.mention} VS {p2.mention}\n\n"
    if last_attack:
        attacker, atk_name, dmg = last_attack
        desc += f"**{attacker.mention}** used **{atk_name}** and dealt **{dmg} dmg**!\n\n"

    embed = discord.Embed(title="Skibidi Battle! 🚽⚔️", description=desc, color=discord.Color.red())
    embed.add_field(name=f"{c1['name']} ({p1.display_name})", value=f"❤️ {c1['hp']} HP", inline=True)
    embed.add_field(name=f"{c2['name']} ({p2.display_name})", value=f"❤️ {c2['hp']} HP", inline=True)

    turn_player = p1 if game["turn"] == p1.id else p2
    view = AttackView(turn_player, p2 if turn_player == p1 else p1, game)

    if "message" not in game:
        vs_image = await make_vs_image(c1["image"], c2["image"])
        filename = f"{c1['name']}_VS_{c2['name']}.png"
        file = discord.File(vs_image, filename="vs.png")
        msg = await channel.send(file=file, embed=embed, view=view)
        game["message"] = msg
    else:
        await game["message"].edit(embed=embed, view=view)

# ================= Commands =================
class Skibidi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="skibidi")
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
            await interaction.response.send_message(embed=confirm_embed, view=view)
        else:
            await channel.send(embed=confirm_embed, view=view)

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