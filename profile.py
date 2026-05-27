import os
import random
from io import BytesIO

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont


def image_file(img: Image.Image, filename: str) -> discord.File:
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename=filename)


from database import (
    cursor,
    get_coins,
    get_bank,
    get_wins,
    get_losses
)


# =========================
# FONTS
# =========================
def load_fonts():
    try:
        title = ImageFont.truetype("arial.ttf", 54)
        big = ImageFont.truetype("arial.ttf", 38)
        med = ImageFont.truetype("arial.ttf", 28)
        small = ImageFont.truetype("arial.ttf", 22)
        tiny = ImageFont.truetype("arial.ttf", 18)
    except:
        title = ImageFont.load_default()
        big = ImageFont.load_default()
        med = ImageFont.load_default()
        small = ImageFont.load_default()
        tiny = ImageFont.load_default()

    return title, big, med, small, tiny


def draw_center(draw, box, text, font, fill):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = x1 + ((x2 - x1 - tw) / 2)
    y = y1 + ((y2 - y1 - th) / 2)
    draw.text((x, y), text, fill=fill, font=font)


def shorten(text, limit=18):
    return text if len(text) <= limit else text[:limit - 3] + "..."


# =========================
# RANK SYSTEM
# =========================
def get_global_rank(user_id):
    wallet = get_coins(user_id)
    bank = get_bank(user_id)
    networth = wallet + bank

    cursor.execute("""
        SELECT COUNT(*)
        FROM economy
        WHERE (coins + bank) > ?
    """, (networth,))

    return cursor.fetchone()[0] + 1


def get_server_rank(user_id, guild):
    if not guild:
        return "N/A"

    wallet = get_coins(user_id)
    bank = get_bank(user_id)
    target_networth = wallet + bank

    guild_ids = {member.id for member in guild.members if not member.bot}

    cursor.execute("""
        SELECT user_id, coins, bank
        FROM economy
    """)

    rows = cursor.fetchall()

    server_users = []
    for uid, coins, bank_amount in rows:
        if uid in guild_ids:
            server_users.append((uid, coins + bank_amount))

    server_users.sort(key=lambda x: x[1], reverse=True)

    for rank, (uid, networth) in enumerate(server_users, start=1):
        if uid == user_id:
            return rank

    higher = sum(1 for _, networth in server_users if networth > target_networth)
    return higher + 1


# =========================
# AVATAR
# =========================
async def get_avatar_image(user):
    try:
        avatar_asset = user.display_avatar.with_size(256)
        avatar_bytes = await avatar_asset.read()

        avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((150, 150))

        mask = Image.new("L", (150, 150), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 150, 150), fill=255)

        return avatar, mask

    except:
        return None, None


# =========================
# PROFILE IMAGE
# =========================
async def make_profile_card(user, guild):
    wallet = get_coins(user.id)
    bank = get_bank(user.id)
    networth = wallet + bank

    wins = get_wins(user.id)
    losses = get_losses(user.id)

    total_games = wins + losses
    winrate = round((wins / total_games) * 100, 1) if total_games > 0 else 0

    global_rank = get_global_rank(user.id)
    server_rank = get_server_rank(user.id, guild)

    width, height = 1150, 680

    img = Image.new("RGB", (width, height), (14, 14, 24))
    draw = ImageDraw.Draw(img)

    font_title, font_big, font_med, font_small, font_tiny = load_fonts()

    gold = (255, 215, 90)
    white = (240, 240, 240)
    muted = (170, 170, 185)
    panel = (30, 30, 48)
    dark = (20, 20, 34)
    outline = (95, 95, 145)

    # Main frame
    draw.rounded_rectangle(
        (20, 20, 1130, 660),
        radius=32,
        fill=panel,
        outline=gold,
        width=6
    )

    # Header
    draw_center(
        draw,
        (0, 35, width, 95),
        "STATE BANK",
        font_title,
        gold
    )

    draw_center(
        draw,
        (0, 88, width, 125),
        "Official Economy Profile",
        font_small,
        muted
    )

    # Left profile panel
    draw.rounded_rectangle(
        (65, 145, 380, 610),
        radius=24,
        fill=dark,
        outline=outline,
        width=3
    )

    avatar, mask = await get_avatar_image(user)

    if avatar and mask:
        img.paste(avatar, (147, 175), mask)
        draw.ellipse((147, 175, 297, 325), outline=gold, width=5)
    else:
        draw.ellipse((147, 175, 297, 325), fill=(45, 45, 65), outline=gold, width=5)
        draw_center(draw, (147, 175, 297, 325), "?", font_title, white)

    draw_center(
        draw,
        (80, 345, 365, 390),
        shorten(user.display_name, 20),
        font_big,
        white
    )

    draw_center(
        draw,
        (80, 390, 365, 425),
        f"ID: {user.id}",
        font_tiny,
        muted
    )

    draw.rounded_rectangle(
        (105, 455, 340, 510),
        radius=16,
        fill=(45, 35, 18),
        outline=gold,
        width=3
    )

    draw_center(
        draw,
        (105, 455, 340, 510),
        "BANK MEMBER",
        font_small,
        gold
    )

    draw_center(
        draw,
        (80, 535, 365, 575),
        "State Bank",
        font_small,
        muted
    )

    # Right stats panel
    draw.rounded_rectangle(
        (420, 145, 1085, 610),
        radius=24,
        fill=dark,
        outline=outline,
        width=3
    )

    # Big net worth box
    draw.rounded_rectangle(
        (455, 175, 1050, 265),
        radius=20,
        fill=(38, 38, 60),
        outline=gold,
        width=4
    )

    draw.text((485, 190), "NET WORTH", fill=gold, font=font_small)
    draw.text((485, 220), f"{networth:,} Coins", fill=white, font=font_big)

    # Stat boxes
    boxes = [
        ("Wallet", f"{wallet:,}", 455, 300),
        ("Bank", f"{bank:,}", 760, 300),
        ("Wins", f"{wins:,}", 455, 405),
        ("Losses", f"{losses:,}", 760, 405),
        ("Win Rate", f"{winrate}%", 455, 510),
        ("Games", f"{total_games:,}", 760, 510),
    ]

    for label, value, x, y in boxes:
        draw.rounded_rectangle(
            (x, y, x + 265, y + 78),
            radius=18,
            fill=(34, 34, 54),
            outline=(75, 75, 115),
            width=3
        )

        draw.text((x + 22, y + 12), label.upper(), fill=gold, font=font_tiny)
        draw.text((x + 22, y + 38), value, fill=white, font=font_small)

    # Rank strip
    draw.rounded_rectangle(
        (455, 595, 1050, 635),
        radius=14,
        fill=(24, 24, 38),
        outline=gold,
        width=2
    )

    rank_text = f"Global Rank: #{global_rank}     Server Rank: #{server_rank}"
    draw_center(draw, (455, 595, 1050, 635), rank_text, font_small, gold)

    return image_file(img, "state_bank_profile.png")


# =========================
# COG
# =========================
class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def build_profile_response(self, user, guild):
        file = await make_profile_card(user, guild)

        embed = discord.Embed(
            color=discord.Color.gold()
        )

        embed.set_image(url="attachment://state_bank_profile.png")

        return embed, file

    @discord.app_commands.command(
        name="profile",
        description="🏦 View your State Bank profile card"
    )
    async def profile_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        await interaction.response.defer()

        user = member or interaction.user

        embed, file = await self.build_profile_response(
            user,
            interaction.guild
        )

        await interaction.followup.send(embed=embed, file=file)

    @commands.command(name="profile")
    async def profile_prefix(
        self,
        ctx,
        member: discord.Member = None
    ):
        user = member or ctx.author

        embed, file = await self.build_profile_response(
            user,
            ctx.guild
        )

        await ctx.send(embed=embed, file=file)


async def setup(bot):
    await bot.add_cog(Profile(bot))