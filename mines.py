
import io
import random
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

from database import get_coins, add_coins, remove_coins, add_win, add_loss

BRAND = "State Bank"

ROWS = 4
COLS = 5
TILES = ROWS * COLS

MIN_BET = 100
MAX_BET = 10_000_000_000_000
MIN_MINES = 1
MAX_MINES = 10
HOUSE_EDGE = 0.94

active_games = {}


def fmt(amount: int):
    return f"{int(amount):,}"


def font(size: int, bold: bool = False):
    for name in ["arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def multiplier(mines: int, safe: int):
    if safe <= 0:
        return 1.0

    safe_tiles = TILES - mines
    mult = 1.0

    for i in range(safe):
        den = safe_tiles - i
        if den <= 0:
            break
        mult *= (TILES - i) / den

    return round(mult * HOUSE_EDGE, 2)


def center(draw, box, text, fnt, fill):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2), text, font=fnt, fill=fill)


def make_image(user_name, bet, mines, revealed, mine_tiles, over, mult, payout, status, status_color):
    W, H = 1200, 760
    navy = (8, 12, 28)
    panel = (18, 24, 52)
    panel2 = (25, 31, 68)
    gold = (244, 201, 92)
    white = (245, 245, 245)
    muted = (172, 178, 200)
    hidden = (35, 42, 90)
    border = (94, 106, 170)
    green = (73, 210, 128)
    red = (220, 74, 74)

    img = Image.new("RGB", (W, H), navy)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        r = int(11 - (y / H) * 6)
        g = int(17 - (y / H) * 8)
        b = int(42 - (y / H) * 20)
        draw.line((0, y, W, y), fill=(r, g, b))

    f_title = font(50, True)
    f_med = font(28, True)
    f_small = font(20, True)
    f_tiny = font(18)
    f_cell = font(34, True)
    f_status = font(38, True)

    draw.rounded_rectangle((20, 20, W - 20, H - 20), radius=28, outline=gold, width=5)
    draw.text((W // 2, 62), f"{BRAND.upper()} MINES", font=f_title, fill=gold, anchor="mm")
    draw.text((W // 2, 110), "Reveal gems, avoid mines, cash out before you lose.", font=f_tiny, fill=muted, anchor="mm")

    draw.rounded_rectangle((55, 150, 345, 660), radius=22, fill=panel, outline=border, width=3)
    info = [
        ("PLAYER", user_name[:18]),
        ("BET", f"{fmt(bet)} Coins"),
        ("MINES", str(mines)),
        ("SAFE", str(len(revealed))),
        ("MULTI", f"x{mult:.2f}"),
    ]

    y = 185
    for label, value in info:
        draw.text((85, y), label, font=f_small, fill=gold)
        draw.text((85, y + 32), value, font=f_med, fill=white)
        y += 92

    draw.rounded_rectangle((390, 150, 1145, 660), radius=22, fill=panel2, outline=border, width=3)

    left, top = 455, 210
    size, gap = 105, 15

    for r in range(ROWS):
        for c in range(COLS):
            i = r * COLS + c
            x1 = left + c * (size + gap)
            y1 = top + r * (size + gap)
            x2 = x1 + size
            y2 = y1 + size

            fill = hidden
            outline = border
            text = ""
            text_fill = white

            if i in revealed:
                fill = (232, 237, 245)
                outline = gold
                text = "♦"
                text_fill = green

            if over and i in mine_tiles:
                fill = (132, 31, 45)
                outline = gold
                text = "✹"
                text_fill = white

            draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill=fill, outline=outline, width=4)

            if text:
                draw.text(((x1 + x2) // 2, (y1 + y2) // 2), text, font=f_cell, fill=text_fill, anchor="mm")

    draw.rounded_rectangle((455, 575, 1085, 630), radius=16, fill=(9, 13, 31), outline=status_color, width=3)
    draw.text((770, 602), status, font=f_status, fill=status_color, anchor="mm")

    draw.text((455, 675), f"Potential Cashout: {fmt(payout)} Coins", font=f_med, fill=gold)
    draw.text((W // 2, 725), "State Bank • Mines", font=f_tiny, fill=muted, anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="state_bank_mines.png")


class TileButton(discord.ui.Button):
    def __init__(self, tile: int):
        super().__init__(label=" ", style=discord.ButtonStyle.secondary, row=tile // COLS)
        self.tile = tile

    async def callback(self, interaction: discord.Interaction):
        view: MinesView = self.view

        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("❌ This is not your game.", ephemeral=True)

        if view.finished:
            return await interaction.response.send_message("❌ This game is already over.", ephemeral=True)

        if self.tile in view.mines:
            view.finished = True
            view.status = "BOOM! YOU LOST"
            view.status_color = (220, 74, 74)
            add_loss(view.user.id)
            active_games.pop(view.user.id, None)

            for child in view.children:
                child.disabled = True

            return await interaction.response.edit_message(embed=view.embed(lost=True), attachments=[view.file()], view=view)

        view.revealed.add(self.tile)
        self.disabled = True
        self.label = "♦"
        self.style = discord.ButtonStyle.success

        view.mult = multiplier(view.mine_count, len(view.revealed))
        view.payout = max(int(view.bet * view.mult), view.bet)
        view.status = f"SAFE! x{view.mult:.2f}"
        view.status_color = (73, 210, 128)
        view.cashout.disabled = False

        if len(view.revealed) >= TILES - view.mine_count:
            return await view.cash_out(interaction, auto=True)

        await interaction.response.edit_message(embed=view.embed(), attachments=[view.file()], view=view)


class CashoutButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cash Out", emoji="💰", style=discord.ButtonStyle.blurple, row=4, disabled=True)

    async def callback(self, interaction: discord.Interaction):
        await self.view.cash_out(interaction)


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", emoji="🛑", style=discord.ButtonStyle.red, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: MinesView = self.view

        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("❌ This is not your game.", ephemeral=True)

        if view.revealed:
            return await interaction.response.send_message("❌ You already revealed a tile. Use Cash Out instead.", ephemeral=True)

        view.finished = True
        active_games.pop(view.user.id, None)
        add_coins(view.user.id, view.bet)

        for child in view.children:
            child.disabled = True

        view.status = "CANCELLED - REFUNDED"
        view.status_color = (244, 201, 92)

        await interaction.response.edit_message(embed=view.embed(cancelled=True), attachments=[view.file()], view=view)


class MinesView(discord.ui.View):
    def __init__(self, user: discord.Member, bet: int, mine_count: int):
        super().__init__(timeout=180)
        self.user = user
        self.bet = bet
        self.mine_count = mine_count
        self.mines = set(random.sample(range(TILES), mine_count))
        self.revealed = set()
        self.finished = False
        self.message: Optional[discord.Message] = None
        self.mult = 1.0
        self.payout = bet
        self.status = "PICK A TILE"
        self.status_color = (244, 201, 92)

        for i in range(TILES):
            self.add_item(TileButton(i))

        self.cashout = CashoutButton()
        self.add_item(self.cashout)
        self.add_item(CancelButton())

    def file(self):
        return make_image(
            self.user.display_name,
            self.bet,
            self.mine_count,
            self.revealed,
            self.mines,
            self.finished,
            self.mult,
            self.payout,
            self.status,
            self.status_color,
        )

    def embed(self, lost=False, cashed=False, cancelled=False):
        color = discord.Color.gold()
        if lost:
            color = discord.Color.red()
        if cashed:
            color = discord.Color.green()

        embed = discord.Embed(
            title="💣 State Bank Mines",
            description=f"**Bet:** {fmt(self.bet)} Coins\n**Mines:** {self.mine_count}\n**Safe Picks:** {len(self.revealed)}",
            color=color
        )

        if lost:
            embed.add_field(name="Result", value=f"❌ Lost **{fmt(self.bet)} Coins**.", inline=False)
        elif cashed:
            embed.add_field(name="Cashout", value=f"✅ Cashed out **{fmt(self.payout)} Coins** at **x{self.mult:.2f}**.", inline=False)
        elif cancelled:
            embed.add_field(name="Cancelled", value=f"Refunded **{fmt(self.bet)} Coins**.", inline=False)
        else:
            embed.add_field(name="Potential Cashout", value=f"{fmt(self.payout)} Coins", inline=True)
            embed.add_field(name="Multiplier", value=f"x{self.mult:.2f}", inline=True)

        embed.set_footer(text="State Bank • Reveal gems and cash out before you hit a mine")
        return embed

    async def cash_out(self, interaction: discord.Interaction, auto=False):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your game.", ephemeral=True)

        if self.finished:
            return await interaction.response.send_message("❌ This game is already over.", ephemeral=True)

        if not self.revealed:
            return await interaction.response.send_message("❌ Reveal at least one tile first.", ephemeral=True)

        self.finished = True
        self.status = "AUTO CASHOUT!" if auto else "CASHED OUT!"
        self.status_color = (73, 210, 128)

        add_coins(self.user.id, self.payout)
        add_win(self.user.id)
        active_games.pop(self.user.id, None)

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=self.embed(cashed=True), attachments=[self.file()], view=self)

    async def on_timeout(self):
        if self.finished:
            return

        self.finished = True
        active_games.pop(self.user.id, None)

        for child in self.children:
            child.disabled = True

        if not self.revealed:
            add_coins(self.user.id, self.bet)
            self.status = "TIMEOUT - REFUNDED"
            self.status_color = (244, 201, 92)
            embed = self.embed(cancelled=True)
        else:
            add_coins(self.user.id, self.payout)
            add_win(self.user.id)
            self.status = "TIMEOUT - AUTO CASHOUT"
            self.status_color = (73, 210, 128)
            embed = self.embed(cashed=True)

        if self.message:
            try:
                await self.message.edit(embed=embed, attachments=[self.file()], view=self)
            except Exception:
                pass


class Mines(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def clear_stale(self, user_id: int):
        old = active_games.get(user_id)

        if not old:
            return

        if old.finished or old.message is None:
            active_games.pop(user_id, None)
            return

        try:
            await old.message.channel.fetch_message(old.message.id)
        except Exception:
            active_games.pop(user_id, None)

    async def start_game(self, source, user: discord.Member, bet: int, mines: int):
        await self.clear_stale(user.id)

        if user.id in active_games:
            msg = "❌ You already have an active Mines game. Use `!minescancel` if it is stuck."
            if isinstance(source, discord.Interaction):
                return await source.response.send_message(msg, ephemeral=True)
            return await source.send(msg)

        if bet < MIN_BET or bet > MAX_BET:
            msg = f"❌ Bet must be between **{fmt(MIN_BET)}** and **{fmt(MAX_BET)}** Coins."
            if isinstance(source, discord.Interaction):
                return await source.response.send_message(msg, ephemeral=True)
            return await source.send(msg)

        if mines < MIN_MINES or mines > MAX_MINES:
            msg = f"❌ Mines must be between **{MIN_MINES}** and **{MAX_MINES}**."
            if isinstance(source, discord.Interaction):
                return await source.response.send_message(msg, ephemeral=True)
            return await source.send(msg)

        wallet = get_coins(user.id)

        if wallet < bet:
            msg = f"❌ Not enough Coins. Wallet: **{fmt(wallet)} Coins**"
            if isinstance(source, discord.Interaction):
                return await source.response.send_message(msg, ephemeral=True)
            return await source.send(msg)

        remove_coins(user.id, bet)

        view = MinesView(user, bet, mines)
        active_games[user.id] = view

        if isinstance(source, discord.Interaction):
            await source.response.send_message(embed=view.embed(), file=view.file(), view=view)
            view.message = await source.original_response()
        else:
            view.message = await source.send(embed=view.embed(), file=view.file(), view=view)

    @app_commands.command(name="mines", description="💣 Play State Bank Mines")
    async def mines_slash(self, interaction: discord.Interaction, bet: int, mines: int = 3):
        await self.start_game(interaction, interaction.user, bet, mines)

    @commands.command(name="mines")
    async def mines_prefix(self, ctx, bet: int, mines: int = 3):
        await self.start_game(ctx, ctx.author, bet, mines)

    @app_commands.command(name="mines-cancel", description="🛑 Cancel your stuck Mines game")
    async def mines_cancel_slash(self, interaction: discord.Interaction):
        old = active_games.get(interaction.user.id)

        if not old:
            return await interaction.response.send_message("✅ You do not have an active Mines game.", ephemeral=True)

        if not old.revealed and not old.finished:
            add_coins(interaction.user.id, old.bet)

        old.finished = True
        active_games.pop(interaction.user.id, None)

        await interaction.response.send_message("✅ Mines game cleared. Bet refunded only if no tiles were revealed.", ephemeral=True)

    @commands.command(name="minescancel")
    async def mines_cancel_prefix(self, ctx):
        old = active_games.get(ctx.author.id)

        if not old:
            return await ctx.send("✅ You do not have an active Mines game.")

        if not old.revealed and not old.finished:
            add_coins(ctx.author.id, old.bet)

        old.finished = True
        active_games.pop(ctx.author.id, None)

        await ctx.send("✅ Mines game cleared. Bet refunded only if no tiles were revealed.")


async def setup(bot):
    await bot.add_cog(Mines(bot))
