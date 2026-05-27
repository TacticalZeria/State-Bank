import json
import random
import time
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

from database import get_coins, add_coins, remove_coins

DATA_PATH = Path("data/income_cooldowns.json")

WORK_COOLDOWN = 30 * 60
CRIME_COOLDOWN = 45 * 60
STREET_COOLDOWN = 20 * 60

WORK_SCENARIOS = [
    "You fix grandma's computer by turning it off and back on. She tips you {money} for the hard work.",
    "You handle a long line of customers at State Bank and earn {money}.",
    "You clean the vault floor until it shines like gold and get paid {money}.",
    "You count stacks of bills for three hours and somehow do not lose your mind. You earn {money}.",
    "You help a confused customer reset their PIN and they leave you a bonus of {money}.",
    "You repair a broken ATM that kept eating cards and earn {money}.",
    "You guard the front desk during a busy day and collect {money}.",
    "You file boring bank paperwork perfectly and get rewarded with {money}.",
    "You deliver a sealed envelope across the city for the bank and earn {money}.",
    "You help the manager catch a counting mistake and get a bonus of {money}.",
    "You polish the State Bank sign until it blinds traffic and earn {money}.",
    "You work overtime during the casino rush and walk away with {money}.",
]

STREET_SCENARIOS = [
    "You sell snacks outside the casino floor and make {money}.",
    "You wash cars near the bank entrance and earn {money}.",
    "You help someone carry heavy bags and they tip you {money}.",
    "You run quick errands around town and collect {money}.",
    "You find loose change by the ATM and somehow it adds up to {money}.",
    "You flip old collectibles at a street stand and make {money}.",
    "You help clean up after a block party and get paid {money}.",
    "You sell cold drinks on a hot summer day and earn {money}.",
    "You return a lost wallet and get a thank-you reward of {money}.",
    "You help set up a local event booth and collect {money}.",
    "You do a quick delivery job and earn {money}.",
    "You win a tiny sidewalk raffle and get {money}.",
]

CRIME_SUCCESS_SCENARIOS = [
    "You try a sketchy casino hustle and somehow walk away with {money}.",
    "You sneak into a shady dice game and come out lucky with {money}.",
    "You bluff your way through a backroom card table and win {money}.",
    "You spot a rigged game before anyone else and flip the situation for {money}.",
    "You pull off a risky street scheme and escape with {money}.",
    "You find an abandoned cash envelope behind the casino and keep {money}.",
    "You outsmart a fake chip scam and make {money}.",
    "You make a risky deal near the vault entrance and profit {money}.",
    "You catch someone slipping at the tables and walk away with {money}.",
    "You gamble with bad odds and somehow hit for {money}.",
]

CRIME_FAIL_SCENARIOS = [
    "Security catches you acting suspicious and fines you {money}.",
    "You trip a silent alarm and lose {money}.",
    "Your plan falls apart instantly and costs you {money}.",
    "You get baited by a fake opportunity and lose {money}.",
    "A guard recognizes you immediately and you pay {money} to avoid more trouble.",
    "The dice game was rigged against you and you lose {money}.",
    "You drop the bag while running and lose {money}.",
    "You panic at the worst possible moment and lose {money}.",
    "The casino cameras catch everything and you get fined {money}.",
    "You try to act casual, fail badly, and lose {money}.",
]


def ensure_data_file():
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DATA_PATH.exists():
        DATA_PATH.write_text("{}", encoding="utf-8")


def load_cooldowns():
    ensure_data_file()

    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cooldowns(data):
    ensure_data_file()
    DATA_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_last(user_id: int, command_name: str):
    data = load_cooldowns()
    user_data = data.get(str(user_id), {})
    return float(user_data.get(command_name, 0))


def set_last(user_id: int, command_name: str):
    data = load_cooldowns()
    uid = str(user_id)

    if uid not in data:
        data[uid] = {}

    data[uid][command_name] = time.time()
    save_cooldowns(data)


def time_left(last_used: float, cooldown: int):
    elapsed = time.time() - last_used
    remaining = int(cooldown - elapsed)
    return max(0, remaining)


def format_time(seconds: int):
    seconds = max(0, int(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def reply_id():
    return random.randint(100000, 999999)


def money_text(amount: int):
    return f"💵 **{amount:,}**"


def make_income_embed(user: discord.Member, description: str, color: discord.Color, cooldown: int):
    embed = discord.Embed(
        description=description,
        color=color
    )

    embed.set_author(
        name=user.display_name,
        icon_url=user.display_avatar.url
    )

    embed.set_footer(
        text=f"Reply #{reply_id()} • Cooldown: {format_time(cooldown)}"
    )

    return embed


class Income(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def run_work(self, user: discord.Member):
        remaining = time_left(get_last(user.id, "work"), WORK_COOLDOWN)

        if remaining > 0:
            return None, f"⏳ You can work again in **{format_time(remaining)}**."

        earned = random.randint(900, 3200)
        scenario = random.choice(WORK_SCENARIOS).format(money=money_text(earned))

        add_coins(user.id, earned)
        set_last(user.id, "work")

        description = (
            f"{scenario}\n\n"
            f"🏦 Wallet: **{get_coins(user.id):,} Coins**"
        )

        embed = make_income_embed(
            user,
            description,
            discord.Color.green(),
            WORK_COOLDOWN
        )

        return embed, None

    async def run_street(self, user: discord.Member):
        remaining = time_left(get_last(user.id, "street"), STREET_COOLDOWN)

        if remaining > 0:
            return None, f"⏳ You can do another street hustle in **{format_time(remaining)}**."

        earned = random.randint(300, 1900)
        scenario = random.choice(STREET_SCENARIOS).format(money=money_text(earned))

        add_coins(user.id, earned)
        set_last(user.id, "street")

        description = (
            f"{scenario}\n\n"
            f"🏦 Wallet: **{get_coins(user.id):,} Coins**"
        )

        embed = make_income_embed(
            user,
            description,
            discord.Color.gold(),
            STREET_COOLDOWN
        )

        return embed, None

    async def run_crime(self, user: discord.Member):
        remaining = time_left(get_last(user.id, "crime"), CRIME_COOLDOWN)

        if remaining > 0:
            return None, f"⏳ You can try crime again in **{format_time(remaining)}**."

        wallet = get_coins(user.id)

        if wallet < 500:
            return None, "❌ You need at least **500 Coins** in your wallet to risk crime."

        set_last(user.id, "crime")

        success = random.randint(1, 100) <= 48

        if success:
            earned = random.randint(2000, 9000)
            scenario = random.choice(CRIME_SUCCESS_SCENARIOS).format(money=money_text(earned))

            add_coins(user.id, earned)

            description = (
                f"{scenario}\n\n"
                f"✅ Profit: **+{earned:,} Coins**\n"
                f"🏦 Wallet: **{get_coins(user.id):,} Coins**"
            )

            embed = make_income_embed(
                user,
                description,
                discord.Color.green(),
                CRIME_COOLDOWN
            )

        else:
            fine = random.randint(500, min(3500, max(wallet, 500)))
            scenario = random.choice(CRIME_FAIL_SCENARIOS).format(money=money_text(fine))

            remove_coins(user.id, fine)

            description = (
                f"{scenario}\n\n"
                f"🚨 Lost: **-{fine:,} Coins**\n"
                f"🏦 Wallet: **{get_coins(user.id):,} Coins**"
            )

            embed = make_income_embed(
                user,
                description,
                discord.Color.red(),
                CRIME_COOLDOWN
            )

        return embed, None

    @app_commands.command(
        name="work",
        description="🏦 Work for State Bank money"
    )
    async def work_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed, error = await self.run_work(interaction.user)

        if error:
            return await interaction.followup.send(error, ephemeral=True)

        await interaction.followup.send(embed=embed)

    @commands.command(name="work")
    async def work_prefix(self, ctx):
        embed, error = await self.run_work(ctx.author)

        if error:
            return await ctx.send(error)

        await ctx.send(embed=embed)

    @app_commands.command(
        name="crime",
        description="💀 Try a risky State Bank crime"
    )
    async def crime_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed, error = await self.run_crime(interaction.user)

        if error:
            return await interaction.followup.send(error, ephemeral=True)

        await interaction.followup.send(embed=embed)

    @commands.command(name="crime")
    async def crime_prefix(self, ctx):
        embed, error = await self.run_crime(ctx.author)

        if error:
            return await ctx.send(error)

        await ctx.send(embed=embed)

    @app_commands.command(
        name="street",
        description="💸 Do a street hustle for State Bank money"
    )
    async def street_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed, error = await self.run_street(interaction.user)

        if error:
            return await interaction.followup.send(error, ephemeral=True)

        await interaction.followup.send(embed=embed)

    @commands.command(name="street")
    async def street_prefix(self, ctx):
        embed, error = await self.run_street(ctx.author)

        if error:
            return await ctx.send(error)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Income(bot))
