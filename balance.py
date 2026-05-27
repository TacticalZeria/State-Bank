import discord
from discord.ext import commands
from database import get_coins, get_bank, get_wins, get_losses


class Balance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, user: discord.Member):
        coins = get_coins(user.id)
        bank = get_bank(user.id)
        wins = get_wins(user.id)
        losses = get_losses(user.id)
        total = wins + losses
        winrate = round((wins / total) * 100, 2) if total > 0 else 0

        embed = discord.Embed(
            title=f"🏦 State Bank Profile — {user.display_name}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="💵 Wallet", value=f"{coins:,} Coins", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{bank:,} Coins", inline=True)
        embed.add_field(name="💎 Net Worth", value=f"{coins + bank:,} Coins", inline=False)
        embed.add_field(name="🏆 Wins", value=str(wins), inline=True)
        embed.add_field(name="💀 Losses", value=str(losses), inline=True)
        embed.add_field(name="📊 Win Rate", value=f"{winrate}%", inline=False)
        embed.set_footer(text="State Bank Economy")
        return embed

    @discord.app_commands.command(name="balance", description="🏦 View your State Bank economy profile")
    async def balance_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        user = member or interaction.user
        await interaction.followup.send(embed=self.make_embed(user))

    @commands.command(name="bal", aliases=["balance"])
    async def balance_prefix(self, ctx, member: discord.Member = None):
        user = member or ctx.author
        await ctx.send(embed=self.make_embed(user))


async def setup(bot):
    await bot.add_cog(Balance(bot))
