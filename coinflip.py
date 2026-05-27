import discord
from discord.ext import commands
import random
from io import BytesIO
import os
from PIL import Image, ImageDraw, ImageFont

from database import get_coins, add_coins, remove_coins, add_win, add_loss

MIN_BET = 10
MAX_BET = 250000
CHOICES = ["heads", "tails"]


def image_file(img: Image.Image, filename: str) -> discord.File:
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename=filename)


def load_fonts():
    try:
        return (
            ImageFont.truetype("arial.ttf", 56),
            ImageFont.truetype("arial.ttf", 38),
            ImageFont.truetype("arial.ttf", 26),
            ImageFont.truetype("arial.ttf", 20),
        )
    except:
        return (
            ImageFont.load_default(),
            ImageFont.load_default(),
            ImageFont.load_default(),
            ImageFont.load_default(),
        )


def make_coinflip_image(challenger, opponent, winner, loser, result, bet):
    width, height = 1100, 650
    img = Image.new("RGB", (width, height), (18, 18, 28))
    draw = ImageDraw.Draw(img)

    font_title, font_big, font_med, font_small = load_fonts()

    pot = bet * 2

    draw.rounded_rectangle(
        (20, 20, 1080, 630),
        radius=26,
        fill=(28, 28, 45),
        outline=(220, 180, 70),
        width=5
    )

    draw.rounded_rectangle(
        (55, 105, 1045, 575),
        radius=20,
        fill=(36, 36, 58),
        outline=(90, 90, 120),
        width=3
    )

    draw.text((205, 38), "FLORIDA STATE BANK COINFLIP", fill=(255, 215, 90), font=font_title)

    draw.text((85, 125), f"Challenger: {challenger.display_name}", fill="white", font=font_med)
    draw.text((85, 165), f"Opponent: {opponent.display_name}", fill="white", font=font_med)
    draw.text((85, 205), f"Bet Each: {bet:,} Coins", fill=(255, 215, 90), font=font_med)
    draw.text((85, 245), f"Total Pot: {pot:,} Coins", fill=(255, 215, 90), font=font_med)

    cx, cy = 550, 355
    radius = 115

    coin_color = (255, 210, 70) if result == "heads" else (190, 190, 210)

    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=coin_color,
        outline=(255, 245, 160),
        width=8
    )

    draw.ellipse(
        (cx - 85, cy - 85, cx + 85, cy + 85),
        outline=(120, 95, 40),
        width=4
    )

    face = "H" if result == "heads" else "T"
    draw.text((cx - 22, cy - 38), face, fill=(30, 30, 40), font=font_title)

    draw.rounded_rectangle(
        (145, 485, 955, 555),
        radius=18,
        fill=(20, 20, 32),
        outline=(80, 220, 120),
        width=4
    )

    draw.text(
        (255, 500),
        f"{winner.display_name} WINS +{bet:,} Coins",
        fill=(80, 220, 120),
        font=font_big
    )

    draw.text(
        (410, 565),
        f"Result: {result.upper()}",
        fill="white",
        font=font_small
    )

    return image_file(img, "pvp_coinflip_result.png")


class CoinflipChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, bet):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                "❌ Only the challenged player can accept or decline.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            return

        self.finished = True

        challenger_balance = get_coins(self.challenger.id)
        opponent_balance = get_coins(self.opponent.id)

        if challenger_balance < self.bet:
            for item in self.children:
                item.disabled = True

            return await interaction.response.edit_message(
                content=f"❌ {self.challenger.mention} no longer has enough Coins.",
                embed=None,
                view=self
            )

        if opponent_balance < self.bet:
            for item in self.children:
                item.disabled = True

            return await interaction.response.edit_message(
                content=f"❌ {self.opponent.mention} does not have enough Coins.",
                embed=None,
                view=self
            )

        await interaction.response.defer()

        result = random.choice(CHOICES)
        winner = random.choice([self.challenger, self.opponent])
        loser = self.opponent if winner.id == self.challenger.id else self.challenger

        remove_coins(loser.id, self.bet)
        add_coins(winner.id, self.bet)

        add_win(winner.id)
        add_loss(loser.id)

        file = make_coinflip_image(
            self.challenger,
            self.opponent,
            winner,
            loser,
            result,
            self.bet
        )

        embed = discord.Embed(
            title="🏦 Florida State Bank Coinflip Result",
            description=(
                f"**Winner:** {winner.mention}\n"
                f"**Loser:** {loser.mention}\n"
                f"**Result:** {result.upper()}\n"
                f"**Profit:** +{self.bet:,} Coins"
            ),
            color=discord.Color.gold()
        )

        embed.set_image(url="attachment://pvp_coinflip_result.png")

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(
            content=None,
            embed=embed,
            attachments=[file],
            view=self
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.finished = True

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=f"❌ {self.opponent.mention} declined the coinflip.",
            embed=None,
            view=self
        )


class Coinflip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_pvp_coinflip(self, sender, opponent, bet):
        if opponent.bot:
            return None, "❌ You cannot coinflip bots."

        if sender.id == opponent.id:
            return None, "❌ You cannot coinflip yourself."

        if bet <= 0:
            return None, "❌ Bet must be above 0."

        if bet < MIN_BET:
            return None, f"❌ Minimum bet is **{MIN_BET:,} Coins**."

        if bet > MAX_BET:
            return None, f"❌ Maximum bet is **{MAX_BET:,} Coins**."

        if get_coins(sender.id) < bet:
            return None, f"❌ You don't have enough Coins."

        if get_coins(opponent.id) < bet:
            return None, f"❌ {opponent.mention} does not have enough Coins."

        embed = discord.Embed(
            title="🏦 Florida State Bank Coinflip Challenge",
            description=(
                f"{sender.mention} challenged {opponent.mention}\n\n"
                f"**Bet:** {bet:,} Coins each\n"
                f"**Pot:** {bet * 2:,} Coins\n\n"
                f"{opponent.mention}, accept or decline below."
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="Winner takes profit. Loser pays the bet.")

        view = CoinflipChallengeView(sender, opponent, bet)

        return (embed, view), None

    @discord.app_commands.command(
        name="coinflip",
        description="🏦 Challenge another player to a Florida State Bank coinflip"
    )
    async def coinflip_slash(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        bet: int
    ):
        await interaction.response.defer()

        result, error = await self.start_pvp_coinflip(
            interaction.user,
            opponent,
            bet
        )

        if error:
            return await interaction.followup.send(error, ephemeral=True)

        embed, view = result
        await interaction.followup.send(embed=embed, view=view)

    @commands.command(name="cf")
    async def coinflip_prefix(self, ctx, opponent: discord.Member, bet: int):
        result, error = await self.start_pvp_coinflip(
            ctx.author,
            opponent,
            bet
        )

        if error:
            return await ctx.send(error)

        embed, view = result
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Coinflip(bot))