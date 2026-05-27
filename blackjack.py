from io import BytesIO
import random

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from database import get_coins, add_coins, remove_coins, add_win, add_loss

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠", "♥", "♦", "♣"]
VALUES = {"A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}


def image_file(img: Image.Image, filename: str) -> discord.File:
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename=filename)


def draw_card():
    return random.choice(RANKS), random.choice(SUITS)


def score(hand):
    total = sum(VALUES[card[0]] for card in hand)
    aces = sum(1 for card in hand if card[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def load_fonts():
    try:
        return (
            ImageFont.truetype("arial.ttf", 44),
            ImageFont.truetype("arial.ttf", 30),
            ImageFont.truetype("arial.ttf", 22),
            ImageFont.truetype("arial.ttf", 18),
        )
    except Exception:
        return (ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default())


def draw_center(draw, box, text, font, fill):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x1 + ((x2 - x1 - w) / 2), y1 + ((y2 - y1 - h) / 2)), text, fill=fill, font=font)


def make_table_file(player_name, player, dealer, bet, reveal=False, result=None):
    width, height = 1000, 620
    img = Image.new("RGB", (width, height), (30, 20, 15))
    draw = ImageDraw.Draw(img)
    font_big, font_med, font_small, font_tiny = load_fonts()

    gold = (255, 215, 90)
    panel = (42, 30, 22)
    dark = (18, 18, 26)

    draw.rounded_rectangle((20, 20, 980, 600), radius=28, fill=panel, outline=gold, width=6)
    draw.rounded_rectangle((55, 105, 945, 555), radius=22, fill=dark, outline=(95, 80, 120), width=3)
    draw_center(draw, (0, 32, width, 90), "FLORIDA STATE BANK BLACKJACK", font_big, gold)
    draw.text((70, 115), f"Bet: {bet:,} Coins", fill="white", font=font_med)

    draw.text((70, 165), player_name[:18].upper(), fill="white", font=font_med)
    draw.text((590, 165), "DEALER", fill="white", font=font_med)

    card_w, card_h = 88, 122

    def draw_one(x, y, card, hidden=False):
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=10, fill="white", outline="black", width=3)
        if hidden:
            draw.rounded_rectangle((x + 8, y + 8, x + card_w - 8, y + card_h - 8), radius=8, fill=(40, 80, 180))
            draw_center(draw, (x, y, x + card_w, y + card_h), "?", font_big, "white")
            return
        rank, suit = card
        color = "red" if suit in ["♥", "♦"] else "black"
        draw.text((x + 8, y + 8), rank, fill=color, font=font_small)
        draw_center(draw, (x + 10, y + 36, x + card_w - 10, y + 88), suit, font_big, color)
        draw.text((x + 58, y + 90), rank, fill=color, font=font_tiny)

    def draw_hand(cards, start_x, y, hidden_second=False):
        max_width = 345
        gap = 0 if len(cards) <= 1 else min(95, max(30, (max_width - card_w) // (len(cards) - 1)))
        x = start_x
        for i, card in enumerate(cards):
            draw_one(x, y, card, hidden=(hidden_second and i == 1))
            x += gap

    draw_hand(player, 70, 230)
    draw_hand(dealer, 590, 230, hidden_second=not reveal)

    draw.text((80, 385), f"Value: {score(player)}", fill="white", font=font_med)
    draw.text((590, 385), f"Value: {score(dealer) if reveal else '?'}", fill="white", font=font_med)

    if result:
        draw.rounded_rectangle((230, 485, 770, 545), radius=16, fill=(15, 15, 22), outline=gold, width=3)
        draw_center(draw, (230, 485, 770, 545), result, font_med, gold)

    return image_file(img, "blackjack_table.png")


class BlackjackView(discord.ui.View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.user_id = user.id
        self.bet = bet
        self.player = [draw_card(), draw_card()]
        self.dealer = [draw_card(), draw_card()]

    async def edit_table(self, interaction, reveal=False, result=None, end=False):
        if end:
            for item in self.children:
                item.disabled = True
        file = make_table_file(self.user.display_name, self.player, self.dealer, self.bet, reveal, result)
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url="attachment://blackjack_table.png")
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    async def finish(self, interaction):
        while score(self.dealer) < 17:
            self.dealer.append(draw_card())
        p, d = score(self.player), score(self.dealer)
        if d > 21 or p > d:
            add_win(self.user_id)
            add_coins(self.user_id, self.bet)
            result = f"WIN +{self.bet:,} Coins"
        elif p < d:
            add_loss(self.user_id)
            remove_coins(self.user_id, self.bet)
            result = f"LOSE -{self.bet:,} Coins"
        else:
            result = "PUSH - No Coins Lost"
        await self.edit_table(interaction, reveal=True, result=result, end=True)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your game.", ephemeral=True)
        self.player.append(draw_card())
        if score(self.player) > 21:
            add_loss(self.user_id)
            remove_coins(self.user_id, self.bet)
            return await self.edit_table(interaction, reveal=True, result=f"BUST -{self.bet:,} Coins", end=True)
        await self.edit_table(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your game.", ephemeral=True)
        await self.finish(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.blurple)
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This isn't your game.", ephemeral=True)
        if get_coins(self.user_id) < self.bet:
            return await interaction.response.send_message(f"❌ You need **{self.bet:,} Coins** to double down.", ephemeral=True)
        self.bet *= 2
        self.player.append(draw_card())
        if score(self.player) > 21:
            add_loss(self.user_id)
            remove_coins(self.user_id, self.bet)
            return await self.edit_table(interaction, reveal=True, result=f"DOUBLE BUST -{self.bet:,} Coins", end=True)
        await self.finish(interaction)


class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_game(self, user, bet: int):
        balance = get_coins(user.id)
        if bet <= 0:
            return None, None, "❌ Bet must be above 0."
        if bet > balance:
            return None, None, f"❌ Not enough Coins. Balance: **{balance:,}**"
        view = BlackjackView(self.bot, user, bet)
        file = make_table_file(user.display_name, view.player, view.dealer, bet)
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url="attachment://blackjack_table.png")
        return embed, file, view

    @discord.app_commands.command(name="blackjack", description="🏦 Play Florida State Bank blackjack")
    async def blackjack_slash(self, interaction: discord.Interaction, bet: int):
        await interaction.response.defer()
        embed, file, result = await self.start_game(interaction.user, bet)
        if isinstance(result, str):
            return await interaction.followup.send(result, ephemeral=True)
        await interaction.followup.send(embed=embed, file=file, view=result)

    @commands.command(name="bj")
    async def blackjack_prefix(self, ctx, bet: int):
        embed, file, result = await self.start_game(ctx.author, bet)
        if isinstance(result, str):
            return await ctx.send(result)
        await ctx.send(embed=embed, file=file, view=result)


async def setup(bot):
    await bot.add_cog(Blackjack(bot))
