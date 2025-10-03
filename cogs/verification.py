import discord
from discord.ext import commands
import random, json, os, asyncio
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

DATA_FILE = "/data/verifications.json"
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

# Async lock for thread-safe file writes
save_lock = asyncio.Lock()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

async def save_data(data):
    async with save_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

verification_data = load_data()

def generate_captcha():
    digits = [str(random.randint(0, 9)) for _ in range(5)]
    answer = ''.join(digits)

    width, height = 220, 90
    img = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    fonts = []
    for f in ["arial.ttf", "times.ttf", "comic.ttf", "verdana.ttf"]:
        try:
            fonts.append(ImageFont.truetype(f, 40))
        except:
            pass
    if not fonts:
        fonts = [ImageFont.load_default()]

    # Background noise
    for _ in range(15):
        fake_char = random.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        fx = random.randint(0, width - 20)
        fy = random.randint(0, height - 20)
        fnt = random.choice(fonts)
        draw.text((fx, fy), fake_char, font=fnt, fill=(random.randint(50, 100),) * 3)

    for _ in range(200):
        x, y = random.randint(0, width), random.randint(0, height)
        draw.point((x, y), fill=(random.randint(80, 200), random.randint(80, 200), random.randint(80, 200)))

    for _ in range(5):
        x1, y1, x2, y2 = [random.randint(0, width) for _ in range(4)]
        draw.line((x1, y1, x2, y2), fill=(random.randint(150, 255), 0, random.randint(0, 255)), width=2)

    for _ in range(3):
        x1, y1 = random.randint(0, width - 30), random.randint(0, height - 30)
        x2, y2 = random.randint(x1 + 10, width), random.randint(y1 + 10, height)
        box = [x1, y1, x2, y2]
        draw.arc(box, start=random.randint(0, 180), end=random.randint(180, 360),
                 fill=(0, random.randint(150, 255), random.randint(150, 255)))

    for i, digit in enumerate(digits):
        fnt = random.choice(fonts)
        color = (random.randint(200, 255), random.randint(150, 255), random.randint(0, 255))

        temp_img = Image.new("RGBA", (50, 70), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((5, 5), digit, font=fnt, fill=color)

        rotated = temp_img.rotate(random.randint(-25, 25), expand=1)
        px = 20 + i * 35 + random.randint(-5, 5)
        py = random.randint(5, 20)
        img.paste(rotated, (px, py), rotated)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return answer, discord.File(buffer, filename="captcha.png")

class CaptchaInputView(discord.ui.View):
    def __init__(self, correct_answer, role_id):
        super().__init__(timeout=60)
        self.input = ""
        self.correct_answer = correct_answer
        self.role_id = role_id
        self.attempts = 3

    async def handle_input(self, interaction):
        await interaction.response.edit_message(content=f"Your input: `{self.input}`", view=self)

    # Digit buttons...
    @discord.ui.button(emoji="<:NM1:1423623575729995786>", style=discord.ButtonStyle.secondary, row=0)
    async def one(self, i, b): self.input += "1"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM2:1423623999509893192>", style=discord.ButtonStyle.secondary, row=0)
    async def two(self, i, b): self.input += "2"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM3:1423624284961509438>", style=discord.ButtonStyle.secondary, row=0)
    async def three(self, i, b): self.input += "3"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM4:1423624302795816970>", style=discord.ButtonStyle.secondary, row=1)
    async def four(self, i, b): self.input += "4"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM5:1423624318541234291>", style=discord.ButtonStyle.secondary, row=1)
    async def five(self, i, b): self.input += "5"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM6:1423624335947468874>", style=discord.ButtonStyle.secondary, row=1)
    async def six(self, i, b): self.input += "6"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM7:1423624353005834290>", style=discord.ButtonStyle.secondary, row=2)
    async def seven(self, i, b): self.input += "7"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM8:1423624404239253605>", style=discord.ButtonStyle.secondary, row=2)
    async def eight(self, i, b): self.input += "8"; await self.handle_input(i)
    @discord.ui.button(emoji="<:NM9:1423624427731419146>", style=discord.ButtonStyle.secondary, row=2)
    async def nine(self, i, b): self.input += "9"; await self.handle_input(i)

    @discord.ui.button(emoji="<:Cross6:1277608359868235827>", style=discord.ButtonStyle.danger, row=3)
    async def backspace(self, i, b): self.input = self.input[:-1]; await self.handle_input(i)

    @discord.ui.button(emoji="<:NM0:1423624444949303358>", style=discord.ButtonStyle.secondary, row=3)
    async def zero(self, i, b): self.input += "0"; await self.handle_input(i)

    @discord.ui.button(label="<:CHECK_CHECK_1:1277607864860545094>", style=discord.ButtonStyle.success, row=3)
    async def submit(self, interaction, button):
        role = discord.utils.get(interaction.guild.roles, id=self.role_id)
        if not role:
            return await interaction.response.edit_message(content="⚠️ Role not found. Please contact an admin.", view=None)

        if interaction.guild.me.top_role <= role:
            return await interaction.response.edit_message(content="⚠️ I cannot assign this role due to role hierarchy.", view=None)

        if self.input == self.correct_answer:
            await interaction.user.add_roles(role)
            return await interaction.response.edit_message(content="✅ Verified!", view=None)

        self.attempts -= 1
        if self.attempts > 0:
            answer, file = generate_captcha()
            self.correct_answer = answer
            self.input = ""
            return await interaction.response.edit_message(
                content=f"❌ Incorrect. {self.attempts} attempts left. Try this new one:",
                attachments=[file],
                view=self
            )
        else:
            await interaction.response.edit_message(content="❌ Incorrect. No attempts left.", view=None)
            self.stop()

class VerificationButton(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(label="Verify", emoji=":CHECK_CHECK_1:1277607864860545094>", style=discord.ButtonStyle.green, custom_id="persistent_verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, id=self.role_id)
        if not role:
            return await interaction.response.send_message("⚠️ Verification role not found. Please contact an admin.", ephemeral=True)

        if role in interaction.user.roles:
            return await interaction.response.send_message("✅ You are already verified!", ephemeral=True)

        answer, file = generate_captcha()
        embed = discord.Embed(title="Write colored the number code in the image!")
        embed.set_image(url="attachment://captcha.png")
        await interaction.response.send_message(
            embed=embed,
            file=file,
            view=CaptchaInputView(answer, self.role_id),
            ephemeral=True
        )

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="verification", aliases=["verif", "ver", "verify"])
    @commands.has_permissions(administrator=True)
    async def verification(self, ctx, channel: discord.TextChannel = None, role: discord.Role = None):
        # Usage help
        if not role:
            usage = (
                "❌ Wrong usage.\n\n"
                "**Correct usage:**\n"
                "`$verification @role` → Sets up verification in this channel\n"
                "`$verification #channel @role` → Sets it up in a specific channel"
            )
            return await ctx.send(usage)

        target_channel = channel or ctx.channel

        embed = discord.Embed(
            title="✅ Verification",
            description="Click the button below and answer the question to verify.",
            color=discord.Color.green()
        )
        view = VerificationButton(role.id)
        msg = await target_channel.send(embed=embed, view=view)

        verification_data[str(ctx.guild.id)] = {
            "channel_id": target_channel.id,
            "role_id": role.id,
            "message_id": msg.id
        }
        await save_data(verification_data)
        await ctx.send(f"✅ Verification system set in {target_channel.mention} for role {role.mention}.")

    @commands.Cog.listener()
    async def on_ready(self):
        for guild_id, data in verification_data.items():
            self.bot.add_view(VerificationButton(data["role_id"]))
        print("[Verification] Persistent views restored.")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        for gid, data in list(verification_data.items()):
            if data["channel_id"] == channel.id:
                del verification_data[gid]
                await save_data(verification_data)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        for gid, data in list(verification_data.items()):
            if data.get("message_id") == message.id:
                del verification_data[gid]
                await save_data(verification_data)

async def setup(bot):
    await bot.add_cog(Verification(bot))