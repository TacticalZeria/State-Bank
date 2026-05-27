import discord
from discord.ext import commands
import random
import time

from database import get_coins, add_coins, remove_coins, get_last_rob, set_last_rob

ROB_COOLDOWN = 3600

class Rob(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def run_rob(self, robber, victim):
        if victim.bot:
            return None, "❌ You cannot rob bots."

        if robber.id == victim.id:
            return None, "❌ You cannot rob yourself."

        now = time.time()
        last = get_last_rob(robber.id)

        if now - last < ROB_COOLDOWN:
            remaining = int(ROB_COOLDOWN - (now - last))
            minutes = remaining // 60
            seconds = remaining % 60
            return None, f"⏳ Rob cooldown: **{minutes}m {seconds}s**"

        robber_wallet = get_coins(robber.id)
        victim_wallet = get_coins(victim.id)

        if robber_wallet < 500:
            return None, "❌ You need at least **500 Coins** to rob."

        if victim_wallet < 500:
            return None, f"❌ {victim.mention} is too broke to rob."

        set_last_rob(robber.id)

        if random.randint(1, 100) <= 50:
            stolen = random.randint(250, min(5000, victim_wallet))

            remove_coins(victim.id, stolen)
            add_coins(robber.id, stolen)

            embed = discord.Embed(
                title="💰 Rob Successful",
                description=f"{robber.mention} robbed {victim.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Stolen", value=f"{stolen:,} Coins", inline=False)

        else:
            penalty = random.randint(250, min(2500, robber_wallet))
            remove_coins(robber.id, penalty)

            embed = discord.Embed(
                title="🚨 Rob Failed",
                description=f"{robber.mention} got caught robbing {victim.mention}",
                color=discord.Color.red()
            )
            embed.add_field(name="Fine", value=f"{penalty:,} Coins", inline=False)

        return embed, None

    @commands.command(name="rob")
    async def rob_prefix(self, ctx, member: discord.Member):
        embed, error = await self.run_rob(ctx.author, member)
        if error:
            return await ctx.send(error)
        await ctx.send(embed=embed)

    @discord.app_commands.command(name="rob", description="💀 Attempt to rob another player")
    async def rob_slash(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()

        embed, error = await self.run_rob(interaction.user, member)
        if error:
            return await interaction.followup.send(error, ephemeral=True)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Rob(bot))