import discord from discord.ext import commands import random, json, os, asyncio, math from PIL import Image, ImageDraw, ImageFont, ImageFilter from io import BytesIO from typing import Optional

DATA_FILE = "/data/verifications.json" os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

Async lock for thread-safe file writes

save_lock = asyncio.Lock()

def load_data(): try: if os.path.exists(DATA_FILE): with open(DATA_FILE, "r") as f: return json.load(f) except Exception: pass return {}

async def save_data(data): async with save_lock: with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

verification_data = load_data()

----------------- Image helpers -----------------

def load_font(size: int) -> ImageFont.FreeTypeFont: # common fonts on linux/windows. Pillow will raise if not found. candidates = [ "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "FreeSans.ttf", ] for name in candidates: try: return ImageFont.truetype(name, size) except Exception: continue return ImageFont.load_default()

def wave_distort(img: Image.Image, amplitude=6, wavelength=30, phase=None) -> Image.Image: phase = phase if phase is not None else random.random() * 2 * math.pi w, h = img.size new = Image.new("RGB", (w + amplitude * 2, h), (30, 30, 30)) for y in range(h): offset = int(amplitude * math.sin(2 * math.pi * y / wavelength + phase)) row = img.crop((0, y, w, y + 1)) new.paste(row, (amplitude + offset, y)) # crop back to original width, keep overlap margin left = amplitude // 2 return new.crop((left, 0, left + w, h))

def random_arc(draw: ImageDraw.ImageDraw, w: int, h: int): for _ in range(random.randint(1, 3)): # generate endpoints and then sort them to avoid PIL errors x0 = random.randint(-w // 2, w // 2) y0 = random.randint(0, h) x1 = random.randint(w // 2, w + w // 2) y1 = random.randint(0, h) box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)] start = random.randint(0, 360) end = start + random.randint(60, 300) width = random.randint(1, 4) draw.arc(box, start, end, fill=(random.randint(50, 255),) * 3, width=width)

def add_noise(draw: ImageDraw.ImageDraw, w: int, h: int, dots: int = 150): for _ in range(dots): x = random.randint(0, w - 1) y = random.randint(0, h - 1) r = random.randint(0, 150) draw.point((x, y), fill=(r, r, r))

def generate_captcha(length: int = 5, size=(240, 96)) -> tuple[str, discord.File]: w, h = size # base textured background base = Image.new("RGB", (w, h), (30, 30, 30)) draw = ImageDraw.Draw(base)

# subtle diagonal pattern
for i in range(-w, w, 12):
    draw.line((i, 0, i + w, h), fill=(20, 20, 20))

# pick digits
digits = [str(random.randint(0, 9)) for _ in range(length)]
answer = "".join(digits)

# draw each character on its own layer, then paste
layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
ldraw = ImageDraw.Draw(layer)

x = 20
for ch in digits:
    fsize = random.randint(36, 48)
    try:
        font = load_font(fsize)
    except Exception:
        font = ImageFont.load_default()

    char_w, char_h = ldraw.textsize(ch, font=font)
    char_img = Image.new("RGBA", (char_w + 12, char_h + 12), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(char_img)

    base_col = random.randint(180, 255)
    fill = (base_col, max(0, base_col - random.randint(0, 40)), random.randint(0, 60), 255)
    cdraw.text((6, 6), ch, font=font, fill=fill)

    # rotate and paste
    angle = random.uniform(-28, 28)
    char_img = char_img.rotate(angle, resample=Image.BICUBIC, expand=1)

    # vertical jitter but keep inside image
    max_y = max(8, h - char_img.size[1] - 8)
    y = random.randint(8, max_y) if max_y > 8 else 8
    layer.paste(char_img, (x + random.randint(-6, 6), y), char_img)

    x += int(char_w * random.uniform(0.7, 1.0))

# composite characters over background
combined = Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")
cdraw = ImageDraw.Draw(combined)

# random arcs and lines
random_arc(cdraw, w, h)
for _ in range(random.randint(1, 3)):
    x0 = random.randint(0, max(0, w // 3 - 1))
    y0 = random.randint(0, h - 1)
    x1 = random.randint(max(0, 2 * w // 3), max(1, w - 1))
    y1 = random.randint(0, h - 1)
    cdraw.line((x0, y0, x1, y1), fill=(random.randint(80, 255),) * 3, width=random.randint(1, 3))

add_noise(cdraw, w, h, dots=random.randint(100, 220))

# apply wave distortion
distorted = wave_distort(combined, amplitude=random.randint(4, 9), wavelength=random.randint(18, 40))

# small blur then sharpen to confuse OCR while keeping human readability
distorted = distorted.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 1.1)))
distorted = distorted.filter(ImageFilter.UnsharpMask(radius=1, percent=110, threshold=3))

# save to buffer
buf = BytesIO()
distorted.save(buf, format="PNG")
buf.seek(0)
return answer, discord.File(buf, filename="captcha.png")

----------------- Views and cog -----------------

class CaptchaInputView(discord.ui.View): def init(self, correct_answer: str, role_id: int): super().init(timeout=60) self.input = "" self.correct_answer = correct_answer self.role_id = role_id self.attempts = 3

async def handle_input(self, interaction: discord.Interaction):
    # always update the ephemeral message with current typed input
    await interaction.response.edit_message(content=f"Your input: `{self.input}`", view=self)

@discord.ui.button(label="1️⃣", style=discord.ButtonStyle.secondary, row=0)
async def one(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "1"
    await self.handle_input(interaction)

@discord.ui.button(label="2️⃣", style=discord.ButtonStyle.secondary, row=0)
async def two(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "2"
    await self.handle_input(interaction)

@discord.ui.button(label="3️⃣", style=discord.ButtonStyle.secondary, row=0)
async def three(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "3"
    await self.handle_input(interaction)

@discord.ui.button(label="4️⃣", style=discord.ButtonStyle.secondary, row=1)
async def four(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "4"
    await self.handle_input(interaction)

@discord.ui.button(label="5️⃣", style=discord.ButtonStyle.secondary, row=1)
async def five(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "5"
    await self.handle_input(interaction)

@discord.ui.button(label="6️⃣", style=discord.ButtonStyle.secondary, row=1)
async def six(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "6"
    await self.handle_input(interaction)

@discord.ui.button(label="7️⃣", style=discord.ButtonStyle.secondary, row=2)
async def seven(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "7"
    await self.handle_input(interaction)

@discord.ui.button(label="8️⃣", style=discord.ButtonStyle.secondary, row=2)
async def eight(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "8"
    await self.handle_input(interaction)

@discord.ui.button(label="9️⃣", style=discord.ButtonStyle.secondary, row=2)
async def nine(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "9"
    await self.handle_input(interaction)

@discord.ui.button(label="➖", style=discord.ButtonStyle.danger, row=3)
async def backspace(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input = self.input[:-1]
    await self.handle_input(interaction)

@discord.ui.button(label="0️⃣", style=discord.ButtonStyle.secondary, row=3)
async def zero(self, interaction: discord.Interaction, button: discord.ui.Button):
    self.input += "0"
    await self.handle_input(interaction)

@discord.ui.button(label="🟰", style=discord.ButtonStyle.success, row=3)
async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
    role = discord.utils.get(interaction.guild.roles, id=self.role_id)
    if not role:
        return await interaction.response.edit_message(content="⚠️ Role not found. Please contact an admin.", view=None)

    # Role hierarchy check
    if interaction.guild.me.top_role <= role:
        return await interaction.response.edit_message(content="⚠️ I cannot assign this role due to role hierarchy.", view=None)

    if self.input == self.correct_answer:
        try:
            await interaction.user.add_roles(role)
        except Exception:
            return await interaction.response.edit_message(content="⚠️ Failed to add role. Check my permissions.", view=None)
        return await interaction.response.edit_message(content="✅ Verified!", view=None)

    # wrong answer flow
    self.attempts -= 1
    if self.attempts > 0:
        answer, file = generate_captcha()
        self.correct_answer = answer
        self.input = ""
        embed = discord.Embed(title="Write the number in the image")
        embed.set_image(url="attachment://captcha.png")
        return await interaction.response.edit_message(
            content=f"❌ Incorrect. {self.attempts} attempts left. Try this new one:",
            embed=embed,
            attachments=[file],
            view=self,
        )
    else:
        await interaction.response.edit_message(content="❌ Incorrect. No attempts left.", view=None)
        self.stop()

class VerificationButton(discord.ui.View): def init(self, role_id: int): super().init(timeout=None) self.role_id = role_id

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
    await interaction.response.send_message(embed=embed, file=file, view=CaptchaInputView(answer, self.role_id), ephemeral=True)

class Verification(commands.Cog): def init(self, bot: commands.Bot): self.bot = bot

@commands.command(name="verification", aliases=["verif", "ver", "verify"])
async def verification(self, ctx: commands.Context, *args):
    """Set up verification.

    Usage:
      $verification @role                 -> set verification in current channel
      $verification #channel @role       -> set verification in specified channel
    """
    # If no mentions given, show usage message
    role: Optional[discord.Role] = None
    channel: Optional[discord.TextChannel] = None

    if ctx.message.role_mentions:
        role = ctx.message.role_mentions[0]
    else:
        # try to parse role id or name from args
        for arg in args:
            # mention like <@&id>
            if arg.startswith("<@&") and arg.endswith(">"):
                try:
                    rid = int(arg[3:-1])
                    role = ctx.guild.get_role(rid)
                    if role:
                        break
                except Exception:
                    continue
            # raw id
            if arg.isdigit():
                try:
                    role = ctx.guild.get_role(int(arg))
                    if role:
                        break
                except Exception:
                    continue
        # try by name last
        if not role and args:
            name_try = " ".join(args)
            for r in ctx.guild.roles:
                if r.name.lower() == name_try.lower():
                    role = r
                    break

    if ctx.message.channel_mentions:
        channel = ctx.message.channel_mentions[0]
    else:
        # try to find channel mention/id in args
        for arg in args:
            if arg.startswith("<#") and arg.endswith(">"):
                try:
                    cid = int(arg[2:-1])
                    channel = ctx.guild.get_channel(cid)
                    if channel:
                        break
                except Exception:
                    continue
            if arg.isdigit():
                try:
                    ch = ctx.guild.get_channel(int(arg))
                    if isinstance(ch, discord.TextChannel):
                        channel = ch
                        break
                except Exception:
                    continue

    # default channel to current if none specified
    target_channel = channel or ctx.channel

    usage = (
        "Usage:\n"
        "  $verification @role                 -> set verification in current channel\n"
        "  $verification #channel @role       -> set verification in specified channel"
    )

    # If no role provided, show usage
    if not role:
        return await ctx.send(f"❌ You must mention a role.\n\n{usage}")

    # permission check
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ You need Administrator permission to set up verification.")

    # bot permission check
    if not ctx.guild.me.guild_permissions.manage_roles:
        return await ctx.send("⚠️ I need the Manage Roles permission to assign roles.")

    # role hierarchy check
    if ctx.guild.me.top_role <= role:
        return await ctx.send("⚠️ I cannot assign that role because it is higher than or equal to my top role.\nMove my role above the verification role and try again.")

    # send the message and save config
    embed = discord.Embed(
        title="✅ Verification",
        description="Click the button below and answer the question to verify.",
        color=discord.Color.green(),
    )
    view = VerificationButton(role.id)
    msg = await target_channel.send(embed=embed, view=view)

    verification_data[str(ctx.guild.id)] = {
        "channel_id": target_channel.id,
        "role_id": role.id,
        "message_id": msg.id,
    }
    await save_data(verification_data)
    await ctx.send(f"✅ Verification system set in {target_channel.mention} for role {role.mention}.")

@commands.Cog.listener()
async def on_ready(self):
    # restore persistent views
    for guild_id, data in verification_data.items():
        try:
            rid = int(data.get("role_id"))
            self.bot.add_view(VerificationButton(rid))
        except Exception:
            continue
    print("[Verification] Persistent views restored.")

@commands.Cog.listener()
async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
    for gid, data in list(verification_data.items()):
        if data.get("channel_id") == channel.id:
            del verification_data[gid]
            await save_data(verification_data)

@commands.Cog.listener()
async def on_message_delete(self, message: discord.Message):
    for gid, data in list(verification_data.items()):
        if data.get("message_id") == message.id:
            del verification_data[gid]
            await save_data(verification_data)

async def setup(bot: commands.Bot): await bot.add_cog(Verification(bot))

