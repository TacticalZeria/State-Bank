from io import BytesIO
import random

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

from database import get_coins, add_coins, remove_coins, add_win, add_loss

MIN_BET = 10
MAX_BET = 250000
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BET_TYPES = ["red", "black", "green", "odd", "even", "low", "high"]


def image_file(img: Image.Image, filename: str) -> discord.File:
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename=filename)


def get_color(number: int):
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


def check_win(bet_type: str, number: int):
    color = get_color(number)
    if bet_type == "red" and color == "red": return True, 2
    if bet_type == "black" and color == "black": return True, 2
    if bet_type == "green" and number == 0: return True, 14
    if bet_type == "odd" and number != 0 and number % 2 == 1: return True, 2
    if bet_type == "even" and number != 0 and number % 2 == 0: return True, 2
    if bet_type == "low" and 1 <= number <= 18: return True, 2
    if bet_type == "high" and 19 <= number <= 36: return True, 2
    return False, 0


def load_fonts():
    try:
        return (ImageFont.truetype("arial.ttf", 56), ImageFont.truetype("arial.ttf", 40), ImageFont.truetype("arial.ttf", 28), ImageFont.truetype("arial.ttf", 21))
    except Exception:
        return (ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default())


def draw_center(draw, box, text, font, fill):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((x1 + ((x2-x1-tw)/2), y1 + ((y2-y1-th)/2)), text, fill=fill, font=font)


def make_roulette_file(username, bet, bet_type, number=None, won=None, payout=0, balance=None, filename="roulette.png"):
    width, height = 1200, 720
    img = Image.new("RGB", (width, height), (16, 16, 24))
    draw = ImageDraw.Draw(img)
    font_title, font_big, font_med, font_small = load_fonts()
    gold, panel, dark, outline, white = (255, 215, 90), (30, 30, 46), (20, 20, 32), (105, 105, 160), (240, 240, 240)

    draw.rounded_rectangle((20, 20, 1180, 700), radius=32, fill=panel, outline=gold, width=6)
    draw.rounded_rectangle((60, 110, 1140, 655), radius=26, fill=dark, outline=outline, width=3)
    draw_center(draw, (0, 28, width, 92), "FLORIDA STATE BANK ROULETTE", font_title, gold)

    draw.rounded_rectangle((90, 145, 405, 510), radius=18, fill=(27, 27, 43), outline=outline, width=3)
    draw.text((120, 175), "PLAYER", fill=gold, font=font_small)
    draw.text((120, 210), username[:18], fill=white, font=font_med)
    draw.text((120, 285), "BET", fill=gold, font=font_small)
    draw.text((120, 320), f"{bet:,} Coins", fill=white, font=font_med)
    draw.text((120, 395), "CHOICE", fill=gold, font=font_small)
    draw.text((120, 430), bet_type.upper(), fill=white, font=font_med)

    cx, cy, outer, mid, inner = 770, 330, 185, 150, 82
    draw.ellipse((cx-outer, cy-outer, cx+outer, cy+outer), fill=(78, 55, 30), outline=gold, width=8)
    step = 360 / 37
    for i, num in enumerate(range(37)):
        color = get_color(num)
        fill = (165, 28, 42) if color == "red" else (10, 10, 16) if color == "black" else (20, 145, 75)
        draw.pieslice((cx-mid, cy-mid, cx+mid, cy+mid), -90 + i*step, -90 + (i+1)*step, fill=fill, outline=(220, 220, 220))
    draw.ellipse((cx-inner, cy-inner, cx+inner, cy+inner), fill=(245,245,245), outline=gold, width=5)

    if number is None:
        draw_center(draw, (cx-70, cy-55, cx+70, cy+55), "?", font_title, (20,20,25))
        draw.rounded_rectangle((345, 545, 1095, 635), radius=18, fill=(14,14,24), outline=gold, width=4)
        draw_center(draw, (345, 552, 1095, 595), "READY TO SPIN", font_big, gold)
        draw_center(draw, (345, 598, 1095, 630), "Click the Spin button below to roll the wheel", font_small, white)
    else:
        draw_center(draw, (cx-75, cy-55, cx+75, cy+55), str(number), font_title, (20,20,25))
        landed_color = get_color(number).upper()
        draw.rounded_rectangle((455, 520, 1080, 575), radius=16, fill=(14,14,24), outline=gold, width=3)
        draw_center(draw, (455, 525, 1080, 570), f"LANDED ON {number} ({landed_color})", font_med, gold)
        result_color = (80,230,120) if won else (245,80,80)
        result_text = f"WIN +{payout:,} Coins" if won else f"LOSS -{bet:,} Coins"
        draw.rounded_rectangle((345, 590, 1095, 665), radius=18, fill=(14,14,24), outline=result_color, width=4)
        draw_center(draw, (345, 598, 1095, 648), result_text, font_big, result_color)
        if balance is not None:
            draw.text((120, 555), f"Balance: {balance:,} Coins", fill=white, font=font_med)

    return image_file(img, filename)


class RouletteView(discord.ui.View):
    def __init__(self, user: discord.Member, bet: int, bet_type: str):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        self.bet_type = bet_type
        self.used = False

    @discord.ui.button(label="Spin", style=discord.ButtonStyle.green, emoji="🎡")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your roulette table.", ephemeral=True)
        if self.used:
            return await interaction.response.send_message("❌ You already spun this table.", ephemeral=True)
        balance = get_coins(self.user.id)
        if self.bet > balance:
            return await interaction.response.send_message(f"❌ You no longer have enough Coins.\nBalance: **{balance:,} Coins**", ephemeral=True)
        self.used = True
        number = random.randint(0, 36)
        won, multiplier = check_win(self.bet_type, number)
        if won:
            payout = self.bet * multiplier
            add_coins(self.user.id, payout)
            add_win(self.user.id)
            color = discord.Color.gold()
        else:
            payout = 0
            remove_coins(self.user.id, self.bet)
            add_loss(self.user.id)
            color = discord.Color.red()
        file = make_roulette_file(self.user.display_name, self.bet, self.bet_type, number=number, won=won, payout=payout, balance=get_coins(self.user.id), filename="roulette_result.png")
        embed = discord.Embed(color=color)
        embed.set_image(url="attachment://roulette_result.png")
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your roulette table.", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Roulette cancelled.", embed=None, attachments=[], view=self)


class Roulette(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_game(self, user: discord.Member, bet: int, bet_type: str):
        bet_type = bet_type.lower()
        if bet_type not in BET_TYPES:
            return None, None, None, f"❌ Invalid bet type. Use: `{', '.join(BET_TYPES)}`"
        if bet <= 0:
            return None, None, None, "❌ Bet must be above 0."
        if bet < MIN_BET:
            return None, None, None, f"❌ Minimum bet is **{MIN_BET:,} Coins**."
        if bet > MAX_BET:
            return None, None, None, f"❌ Maximum bet is **{MAX_BET:,} Coins**."
        balance = get_coins(user.id)
        if bet > balance:
            return None, None, None, f"❌ Not enough Coins.\nBalance: **{balance:,} Coins**"
        file = make_roulette_file(user.display_name, bet, bet_type, filename="roulette_ready.png")
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url="attachment://roulette_ready.png")
        return embed, file, RouletteView(user, bet, bet_type), None

    @app_commands.command(name="roulette", description="🏦 Play Florida State Bank roulette")
    @app_commands.describe(bet="How many Coins you want to bet", bet_type="Choose red, black, green, odd, even, low, or high")
    @app_commands.choices(bet_type=[app_commands.Choice(name="Red", value="red"), app_commands.Choice(name="Black", value="black"), app_commands.Choice(name="Green", value="green"), app_commands.Choice(name="Odd", value="odd"), app_commands.Choice(name="Even", value="even"), app_commands.Choice(name="Low 1-18", value="low"), app_commands.Choice(name="High 19-36", value="high")])
    async def roulette_slash(self, interaction: discord.Interaction, bet: int, bet_type: app_commands.Choice[str]):
        await interaction.response.defer()
        embed, file, view, error = await self.create_game(interaction.user, bet, bet_type.value)
        if error:
            return await interaction.followup.send(error, ephemeral=True)
        await interaction.followup.send(embed=embed, file=file, view=view)

    @commands.command(name="roulette")
    async def roulette_prefix(self, ctx, bet: int = None, bet_type: str = None):
        if bet is None or bet_type is None:
            return await ctx.send("❌ Usage: `!roulette <bet> <red/black/green/odd/even/low/high>`")
        embed, file, view, error = await self.create_game(ctx.author, bet, bet_type)
        if error:
            return await ctx.send(error)
        await ctx.send(embed=embed, file=file, view=view)


async def setup(bot):
    await bot.add_cog(Roulette(bot))