from io import BytesIO
import random
import string

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from database import get_coins, add_coins, remove_coins, add_win, add_loss

SYMBOLS = ["cherry", "lemon", "grape", "bell", "diamond", "seven"]
PAYOUTS = {"cherry": 2, "lemon": 2, "grape": 3, "bell": 4, "diamond": 7, "seven": 15}
MIN_BET = 10
MAX_BET = 250000


def image_file(img: Image.Image, filename: str) -> discord.File:
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename=filename)


def clean_text(text: str, limit: int = 18):
    allowed = string.ascii_letters + string.digits + " _-.[]()"
    cleaned = "".join(ch for ch in str(text) if ch in allowed).strip()
    if not cleaned:
        cleaned = "Player"
    return cleaned[:limit]


def short_money(amount: int):
    amount = int(amount)
    if amount >= 1_000_000_000_000:
        text = f"{amount / 1_000_000_000_000:.2f}T"
    elif amount >= 1_000_000_000:
        text = f"{amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        text = f"{amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        text = f"{amount / 1_000:.1f}K"
    else:
        return str(amount)
    return text.replace(".00", "").replace(".0", "")


def load_fonts():
    try:
        return (
            ImageFont.truetype("arial.ttf", 52),
            ImageFont.truetype("arial.ttf", 38),
            ImageFont.truetype("arial.ttf", 28),
            ImageFont.truetype("arial.ttf", 22),
            ImageFont.truetype("arial.ttf", 18),
        )
    except Exception:
        return (
            ImageFont.load_default(),
            ImageFont.load_default(),
            ImageFont.load_default(),
            ImageFont.load_default(),
            ImageFont.load_default(),
        )


def draw_center(draw, box, text, font, fill):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x1 + ((x2 - x1 - tw) / 2), y1 + ((y2 - y1 - th) / 2)), text, fill=fill, font=font)


def draw_symbol(draw, symbol, box, fonts):
    x1, y1, x2, y2 = box
    font_title, font_big, font_med, font_small, font_tiny = fonts
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    gold = (255, 215, 90)
    dark = (18, 18, 26)

    if symbol == "?":
        draw_center(draw, box, "?", font_title, (35, 35, 45))
        return

    if symbol == "seven":
        draw_center(draw, (x1, y1 + 5, x2, y2 - 20), "7", font_title, (185, 25, 40))
        draw_center(draw, (x1, y2 - 38, x2, y2 - 8), "SEVEN", font_tiny, gold)
        return

    if symbol == "diamond":
        points = [(cx, y1 + 24), (x2 - 28, cy), (cx, y2 - 30), (x1 + 28, cy)]
        draw.polygon(points, fill=(55, 190, 255), outline=gold)
        draw.line((cx, y1 + 24, cx, y2 - 30), fill=(230, 250, 255), width=3)
        draw.line((x1 + 28, cy, x2 - 28, cy), fill=(230, 250, 255), width=3)
        draw_center(draw, (x1, y2 - 34, x2, y2 - 8), "DIAMOND", font_tiny, dark)
        return

    if symbol == "bell":
        draw.arc((cx - 45, cy - 58, cx + 45, cy + 42), 190, 350, fill=(210, 160, 35), width=8)
        draw.rounded_rectangle((cx - 45, cy - 15, cx + 45, cy + 35), radius=16, fill=(235, 185, 50), outline=dark, width=4)
        draw.rectangle((cx - 34, cy + 28, cx + 34, cy + 42), fill=(235, 185, 50), outline=dark, width=3)
        draw.ellipse((cx - 10, cy + 35, cx + 10, cy + 55), fill=(120, 80, 20), outline=dark, width=2)
        draw_center(draw, (x1, y2 - 34, x2, y2 - 8), "BELL", font_tiny, dark)
        return

    if symbol == "lemon":
        draw.ellipse((cx - 50, cy - 38, cx + 50, cy + 38), fill=(245, 215, 55), outline=dark, width=4)
        draw.ellipse((cx + 24, cy - 55, cx + 60, cy - 25), fill=(75, 170, 75), outline=dark, width=3)
        draw.arc((cx - 28, cy - 18, cx + 28, cy + 18), 20, 160, fill=(255, 245, 120), width=3)
        draw_center(draw, (x1, y2 - 34, x2, y2 - 8), "LEMON", font_tiny, dark)
        return

    if symbol == "grape":
        purple = (115, 65, 190)
        coords = [(cx - 28, cy - 34), (cx, cy - 34), (cx + 28, cy - 34), (cx - 15, cy - 7), (cx + 15, cy - 7), (cx, cy + 20)]
        for px, py in coords:
            draw.ellipse((px - 18, py - 18, px + 18, py + 18), fill=purple, outline=dark, width=3)
        draw.line((cx, cy - 55, cx - 16, cy - 70), fill=(60, 135, 70), width=5)
        draw.ellipse((cx - 16, cy - 78, cx + 25, cy - 52), fill=(75, 170, 75), outline=dark, width=2)
        draw_center(draw, (x1, y2 - 34, x2, y2 - 8), "GRAPE", font_tiny, dark)
        return

    if symbol == "cherry":
        red = (190, 30, 45)
        draw.line((cx - 26, cy - 12, cx - 8, cy - 55), fill=(60, 135, 70), width=5)
        draw.line((cx + 26, cy - 12, cx - 8, cy - 55), fill=(60, 135, 70), width=5)
        draw.ellipse((cx - 55, cy - 12, cx - 5, cy + 38), fill=red, outline=dark, width=4)
        draw.ellipse((cx + 5, cy - 12, cx + 55, cy + 38), fill=red, outline=dark, width=4)
        draw.ellipse((cx - 34, cy, cx - 22, cy + 12), fill=(255, 110, 120))
        draw.ellipse((cx + 26, cy, cx + 38, cy + 12), fill=(255, 110, 120))
        draw_center(draw, (x1, y2 - 34, x2, y2 - 8), "CHERRY", font_tiny, dark)
        return


def calculate_slots(bet, reels):
    if reels[0] == reels[1] == reels[2]:
        multiplier = PAYOUTS[reels[0]]
        return True, bet * multiplier, f"JACKPOT x{multiplier}"
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        return True, bet // 2, "SMALL MATCH"
    return False, bet, "NO MATCH"


def make_slots_file(username, reels, bet, won=None, amount=0, result_text="READY", new_balance=None, filename="slots.png"):
    width, height = 1100, 650
    img = Image.new("RGB", (width, height), (10, 12, 22))
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()
    font_title, font_big, font_med, font_small, font_tiny = fonts
    gold = (255, 215, 90)
    white = (238, 238, 245)
    muted = (165, 165, 185)
    panel = (26, 28, 45)
    dark = (15, 16, 28)
    outline = (95, 95, 145)

    draw.rounded_rectangle((20, 20, 1080, 630), radius=30, fill=panel, outline=gold, width=6)
    draw_center(draw, (0, 35, width, 90), "FLORIDA STATE BANK SLOTS", font_title, gold)
    draw.rounded_rectangle((65, 115, 1035, 590), radius=24, fill=dark, outline=outline, width=3)

    player = clean_text(username, 20)
    draw.rounded_rectangle((100, 145, 425, 225), radius=16, fill=(32, 34, 55), outline=(75, 75, 115), width=2)
    draw.text((125, 158), "PLAYER", fill=gold, font=font_tiny)
    draw.text((125, 185), player, fill=white, font=font_small)

    draw.rounded_rectangle((675, 145, 1000, 225), radius=16, fill=(32, 34, 55), outline=(75, 75, 115), width=2)
    draw.text((700, 158), "BET", fill=gold, font=font_tiny)
    draw.text((700, 185), f"{short_money(bet)} Coins", fill=white, font=font_small)

    reel_boxes = [(210, 270, 370, 430), (470, 270, 630, 430), (730, 270, 890, 430)]
    for box, symbol in zip(reel_boxes, reels):
        draw.rounded_rectangle(box, radius=22, fill=(245, 245, 238), outline=gold, width=5)
        draw_symbol(draw, symbol, box, fonts)

    if won is None:
        status_color = gold
        status_title = "READY"
        status_line = "Click Spin to start"
    elif won:
        status_color = (80, 230, 120)
        status_title = result_text
        status_line = f"WIN +{short_money(amount)} Coins"
    else:
        status_color = (245, 80, 80)
        status_title = result_text
        status_line = f"LOSS -{short_money(amount)} Coins"

    draw.rounded_rectangle((210, 470, 890, 545), radius=18, fill=(12, 13, 24), outline=status_color, width=4)
    draw_center(draw, (210, 476, 890, 512), status_title, font_big, gold)
    draw_center(draw, (210, 512, 890, 540), status_line, font_small, status_color)

    if new_balance is not None:
        draw_center(draw, (0, 558, width, 590), f"Balance: {short_money(new_balance)} Coins", font_small, muted)

    return image_file(img, filename)


class SlotsView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        self.spun = False

    @discord.ui.button(label="Spin", style=discord.ButtonStyle.green, emoji="🎰")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your slot machine.", ephemeral=True)
        if self.spun:
            return await interaction.response.send_message("❌ You already spun.", ephemeral=True)

        balance = get_coins(self.user.id)
        if self.bet > balance:
            return await interaction.response.send_message(f"❌ You no longer have enough Coins.\nBalance: **{balance:,} Coins**", ephemeral=True)

        await interaction.response.defer()
        self.spun = True

        reels = [random.choice(SYMBOLS), random.choice(SYMBOLS), random.choice(SYMBOLS)]
        won, amount, result_text = calculate_slots(self.bet, reels)

        if won:
            add_coins(self.user.id, amount)
            add_win(self.user.id)
            color = discord.Color.gold()
        else:
            remove_coins(self.user.id, amount)
            add_loss(self.user.id)
            color = discord.Color.red()

        new_balance = get_coins(self.user.id)
        file = make_slots_file(self.user.display_name, reels, self.bet, won, amount, result_text, new_balance, filename="slots_result.png")
        embed = discord.Embed(color=color)
        embed.set_image(url="attachment://slots_result.png")

        for item in self.children:
            item.disabled = True

        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your slot machine.", ephemeral=True)

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(content="❌ Slots cancelled.", embed=None, attachments=[], view=self)


class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_slots(self, user, bet: int):
        balance = get_coins(user.id)
        if bet <= 0:
            return None, None, None, "❌ Bet must be above 0."
        if bet < MIN_BET:
            return None, None, None, f"❌ Minimum bet is **{MIN_BET:,} Coins**."
        if bet > MAX_BET:
            return None, None, None, f"❌ Maximum bet is **{MAX_BET:,} Coins**."
        if bet > balance:
            return None, None, None, f"❌ Not enough Coins.\nBalance: **{balance:,} Coins**"

        file = make_slots_file(user.display_name, ["?", "?", "?"], bet, filename="slots_ready.png")
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url="attachment://slots_ready.png")
        view = SlotsView(user, bet)
        return embed, file, view, None

    @discord.app_commands.command(name="slots", description="🎰 Play Florida State Bank slots")
    async def slots_slash(self, interaction: discord.Interaction, bet: int):
        await interaction.response.defer()
        embed, file, view, error = await self.start_slots(interaction.user, bet)
        if error:
            return await interaction.followup.send(error, ephemeral=True)
        await interaction.followup.send(embed=embed, file=file, view=view)

    @commands.command(name="slots")
    async def slots_prefix(self, ctx, bet: int = None):
        if bet is None:
            return await ctx.send("❌ Usage: `!slots <bet>`")
        embed, file, view, error = await self.start_slots(ctx.author, bet)
        if error:
            return await ctx.send(error)
        await ctx.send(embed=embed, file=file, view=view)


async def setup(bot):
    await bot.add_cog(Slots(bot))
