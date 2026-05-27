import discord
from discord.ext import commands
from discord import app_commands

from database import get_coins, get_bank, withdraw_coins


class Withdraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def run_withdraw(self, user_id: int, amount: str):
        bank = get_bank(user_id)
        if amount.lower() == "all":
            amount = bank
        else:
            try:
                amount = int(amount)
            except ValueError:
                return None, "❌ Invalid amount."

        if not withdraw_coins(user_id, amount):
            return None, "❌ You can't withdraw that amount."

        embed = discord.Embed(
            title="🏦 Florida State Bank — Withdrawal Successful",
            description=f"Withdrew **{amount:,} Coins**",
            color=discord.Color.blurple()
        )
        embed.add_field(name="💰 Wallet", value=f"{get_coins(user_id):,}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{get_bank(user_id):,}", inline=True)
        return embed, None

    @commands.command(name="with")
    async def withdraw_prefix(self, ctx, amount: str):
        embed, error = await self.run_withdraw(ctx.author.id, amount)
        if error:
            return await ctx.send(error)
        await ctx.send(embed=embed)

    @app_commands.command(name="withdraw", description="🏦 Withdraw Coins from Florida State Bank")
    async def withdraw_slash(self, interaction: discord.Interaction, amount: str):
        await interaction.response.defer()
        embed, error = await self.run_withdraw(interaction.user.id, amount)
        if error:
            return await interaction.followup.send(error, ephemeral=True)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Withdraw(bot))
