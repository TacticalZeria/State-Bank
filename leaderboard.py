import discord
from discord.ext import commands
from database import cursor, get_coins, get_bank


def short_money(amount: int):
    amount = int(amount)

    if amount >= 1_000_000_000_000:
        text = f"{amount / 1_000_000_000_000:.2f}T"
    elif amount >= 1_000_000_000:
        text = f"{amount / 1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        text = f"{amount / 1_000_000:.2f}M"
    elif amount >= 1_000:
        text = f"{amount / 1_000:.1f}K"
    else:
        return str(amount)

    return text.replace(".00", "").replace(".0", "")


class LeaderboardView(discord.ui.View):
    def __init__(self, bot, global_data, server_data):
        super().__init__(timeout=120)
        self.bot = bot
        self.global_data = global_data
        self.server_data = server_data

    async def build_embed(self, data, title, user_id):
        top_10 = data[:10]

        embed = discord.Embed(
            title=title,
            color=discord.Color.gold()
        )

        if not top_10:
            embed.description = "No leaderboard data yet."
            return embed

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }

        lines = []

        for rank, (uid, total) in enumerate(top_10, start=1):
            user = self.bot.get_user(uid)
            name = user.name if user else f"User {uid}"
            medal = medals.get(rank, f"#{rank}")

            lines.append(
                f"{medal} **{name}** — 💰 **{short_money(total)}**"
            )

        embed.description = "\n\n".join(lines)

        user_rank = None
        user_total = get_coins(user_id) + get_bank(user_id)

        for rank, (uid, total) in enumerate(data, start=1):
            if uid == user_id:
                user_rank = rank
                user_total = total
                break

        rank_text = f"#{user_rank}" if user_rank else "Unranked"

        embed.set_footer(
            text=f"State Bank • Your Rank: {rank_text} • Total: {short_money(user_total)}"
        )

        return embed

    @discord.ui.button(label="🌍 Global", style=discord.ButtonStyle.green)
    async def global_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.build_embed(
            self.global_data,
            "🏦 State Bank Global Leaderboard",
            interaction.user.id
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏠 Server", style=discord.ButtonStyle.blurple)
    async def server_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.build_embed(
            self.server_data,
            "🏦 State Bank Server Leaderboard",
            interaction.user.id
        )

        await interaction.response.edit_message(embed=embed, view=self)


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def build_leaderboard(self, user_id, guild):
        cursor.execute("""
            SELECT
                user_id,
                (coins + bank) AS total
            FROM economy
            ORDER BY total DESC
            LIMIT 50
        """)

        global_data = cursor.fetchall()

        cursor.execute("""
            SELECT
                user_id,
                (coins + bank) AS total
            FROM economy
            ORDER BY total DESC
            LIMIT 500
        """)

        raw = cursor.fetchall()

        guild_ids = {m.id for m in guild.members if not m.bot} if guild else set()
        server_data = [(uid, total) for (uid, total) in raw if uid in guild_ids]

        view = LeaderboardView(self.bot, global_data, server_data)

        embed = await view.build_embed(
            global_data,
            "🏦 State Bank Global Leaderboard",
            user_id
        )

        return embed, view

    @discord.app_commands.command(
        name="leaderboard",
        description="🏦 View State Bank economy leaderboard"
    )
    async def leaderboard_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed, view = await self.build_leaderboard(
            interaction.user.id,
            interaction.guild
        )

        await interaction.followup.send(embed=embed, view=view)

    @commands.command(name="lb", aliases=["leaderboard"])
    async def leaderboard_prefix(self, ctx):
        embed, view = await self.build_leaderboard(
            ctx.author.id,
            ctx.guild
        )

        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))