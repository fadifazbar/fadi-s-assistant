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

    img = Image.new("RGB", (200, 80), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # Better font (fallback to default if not found)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        font = ImageFont.load_default()

    # Background noise digits
    for _ in range(10):
        fake_digit = str(random.randint(0, 9))
        x = random.randint(0, 180)
        y = random.randint(0, 60)
        draw.text((x, y), fake_digit, font=font, fill=(100, 100, 100))

    # Noise dots
    for _ in range(50):
        x, y = random.randint(0, 200), random.randint(0, 80)
        draw.point((x, y), fill=(random.randint(50, 200),) * 3)

    # Real digits
    for i, digit in enumerate(digits):
        x = 20 + i * 30 + random.randint(-5, 5)
        y = random.randint(10, 30)
        draw.text((x, y), digit, font=font, fill=(255, 255, 0))

    # Obfuscation line
    draw.line((10, 40, 190, 40), fill=(255, 0, 0), width=2)

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

    @discord.ui.button(label="1️⃣", style=discord.ButtonStyle.secondary, row=0)
    async def one(self, i, b): self.input += "1"; await self.handle_input(i)
    @discord.ui.button(label="2️⃣", style=discord.ButtonStyle.secondary, row=0)
    async def two(self, i, b): self.input += "2"; await self.handle_input(i)
    @discord.ui.button(label="3️⃣", style=discord.ButtonStyle.secondary, row=0)
    async def three(self, i, b): self.input += "3"; await self.handle_input(i)
    @discord.ui.button(label="4️⃣", style=discord.ButtonStyle.secondary, row=1)
    async def four(self, i, b): self.input += "4"; await self.handle_input(i)
    @discord.ui.button(label="5️⃣", style=discord.ButtonStyle.secondary, row=1)
    async def five(self, i, b): self.input += "5"; await self.handle_input(i)
    @discord.ui.button(label="6️⃣", style=discord.ButtonStyle.secondary, row=1)
    async def six(self, i, b): self.input += "6"; await self.handle_input(i)
    @discord.ui.button(label="7️⃣", style=discord.ButtonStyle.secondary, row=2)
    async def seven(self, i, b): self.input += "7"; await self.handle_input(i)
    @discord.ui.button(label="8️⃣", style=discord.ButtonStyle.secondary, row=2)
    async def eight(self, i, b): self.input += "8"; await self.handle_input(i)
    @discord.ui.button(label="9️⃣", style=discord.ButtonStyle.secondary, row=2)
    async def nine(self, i, b): self.input += "9"; await self.handle_input(i)

    @discord.ui.button(label="➖", style=discord.ButtonStyle.danger, row=3)
    async def backspace(self, i, b): self.input = self.input[:-1]; await self.handle_input(i)

    @discord.ui.button(label="0️⃣", style=discord.ButtonStyle.secondary, row=3)
    async def zero(self, i, b): self.input += "0"; await self.handle_input(i)

    @discord.ui.button(label="🟰", style=discord.ButtonStyle.success, row=3)
    async def submit(self, interaction, button):
        role = discord.utils.get(interaction.guild.roles, id=self.role_id)
        if not role:
            return await interaction.response.edit_message(content="⚠️ Role not found. Please contact an admin.", view=None)

        # Role hierarchy check
        if interaction.guild.me.top_role <= role:
            return await interaction.response.edit_message(content="⚠️ I cannot assign this role due to role hierarchy.", view=None)

        if self.input == self.correct_answer:
            await interaction.user.add_roles(role)
            return await interaction.response.edit_message(content="✅ Verified!", view=None)

        self.attempts -= 1
        if self.attempts > 0:
            # New captcha retry
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

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.green, custom_id="persistent_verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, id=self.role_id)
        if not role:
            return await interaction.response.send_message("⚠️ Verification role not found. Please contact an admin.", ephemeral=True)

        if role in interaction.user.roles:
            return await interaction.response.send_message("✅ You are already verified!", ephemeral=True)

        # New captcha
        answer, file = generate_captcha()
        embed = discord.Embed(title="Write the number in the image")
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
        if not role:
            return await ctx.send("❌ You must mention a role.")

        # If no channel is provided, use the one where command is sent
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
        # Restore persistent buttons
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