import discord
from discord.ext import commands
from discord import app_commands

from cogs._statebank_utils import parse_amount, format_money
from database import get_coins, get_bank, deposit_coins


class Deposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def do_deposit(self, user_id: int, amount: str):
        wallet = get_coins(user_id)

        if str(amount).lower().strip() == "all":
            parsed_amount = wallet
        else:
            try:
                parsed_amount = parse_amount(amount, minimum=1)
            except ValueError as e:
                return None, f"❌ {e}"

        if not deposit_coins(user_id, parsed_amount):
            return None, "❌ You can't deposit that amount."

        embed = discord.Embed(
            title="🏦 State Bank — Deposit Successful",
            description=f"Deposited **{format_money(parsed_amount)} Coins**",
            color=discord.Color.green()
        )

        embed.add_field(name="💰 Wallet", value=f"{format_money(get_coins(user_id))}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{format_money(get_bank(user_id))}", inline=True)
        embed.set_footer(text="State Bank • Banking")

        return embed, None

    @commands.command(name="dep")
    async def deposit_prefix(self, ctx, amount: str = None):
        if amount is None:
            return await ctx.send("❌ Usage: `!dep <amount/all>`")

        embed, error = await self.do_deposit(ctx.author.id, amount)

        if error:
            return await ctx.send(error)

        await ctx.send(embed=embed)

    @commands.command(name="deposit")
    async def deposit_full_prefix(self, ctx, amount: str = None):
        await self.deposit_prefix(ctx, amount)

    @app_commands.command(name="deposit", description="🏦 Deposit Coins into State Bank")
    async def deposit_slash(self, interaction: discord.Interaction, amount: str):
        await interaction.response.defer()

        embed, error = await self.do_deposit(interaction.user.id, amount)

        if error:
            return await interaction.followup.send(error, ephemeral=True)

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Deposit(bot))
