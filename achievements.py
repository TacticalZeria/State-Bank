import discord
from discord.ext import commands
from discord import app_commands

from database import unlock_achievement, remove_achievement, get_user_achievements

OWNER_ID = 1125240487507402882


def can_manage_server(member: discord.Member):
    return (
        isinstance(member, discord.Member)
        and (
            member.guild_permissions.manage_guild
            or member.guild_permissions.administrator
        )
    )


def can_use_achievement_action(member: discord.Member, action: str):
    if action == "give":
        return member.id == OWNER_ID
    return can_manage_server(member)

ACHIEVEMENTS = {
    "highest_bidder": {"name": "Highest Bidder", "emoji": "💸", "rarity": "Legendary", "description": "Awarded to the player who makes or wins the highest recorded bid."},
    "high_roller": {"name": "High Roller", "emoji": "🎲", "rarity": "Epic", "description": "Place a massive bet and prove you are not scared of risk."},
    "bank_tycoon": {"name": "Bank Tycoon", "emoji": "🏦", "rarity": "Epic", "description": "Build a serious bank balance inside State Bank."},
    "millionaire": {"name": "Millionaire", "emoji": "💰", "rarity": "Legendary", "description": "Reach a net worth of 1,000,000 Coins."},
    "blackjack_demon": {"name": "Blackjack Demon", "emoji": "🃏", "rarity": "Rare", "description": "Become known for dominating the blackjack table."},
    "slot_addict": {"name": "Slot Addict", "emoji": "🎰", "rarity": "Rare", "description": "Spin the slots enough times to earn casino recognition."},
    "roulette_royalty": {"name": "Roulette Royalty", "emoji": "🎡", "rarity": "Rare", "description": "Win big at the roulette wheel."},
    "coinflip_menace": {"name": "Coinflip Menace", "emoji": "🪙", "rarity": "Rare", "description": "Win PvP coinflips and make people scared to challenge you."},
    "most_wanted": {"name": "Most Wanted", "emoji": "🚨", "rarity": "Epic", "description": "Earn a reputation through robberies and risky moves."},
    "broke_legend": {"name": "Broke Legend", "emoji": "💀", "rarity": "Common", "description": "Lose almost everything but somehow stay in the game."},
    "founding_member": {"name": "Founding Member", "emoji": "⭐", "rarity": "Exclusive", "description": "An early member of State Bank."},
    "casino_elite": {"name": "Casino Elite", "emoji": "👑", "rarity": "Mythic", "description": "Reserved for the most dominant players in the economy."}
}


def rarity_color(rarity: str):
    colors = {
        "Common": discord.Color.light_grey(),
        "Rare": discord.Color.blue(),
        "Epic": discord.Color.purple(),
        "Legendary": discord.Color.gold(),
        "Mythic": discord.Color.red(),
        "Exclusive": discord.Color.teal(),
    }
    return colors.get(rarity, discord.Color.gold())


class AchievementSelect(discord.ui.Select):
    def __init__(self, target: discord.Member, action: str):
        self.target = target
        self.action = action

        options = [
            discord.SelectOption(
                label=data["name"],
                value=achievement_id,
                emoji=data["emoji"],
                description=f"{data['rarity']} achievement"
            )
            for achievement_id, data in ACHIEVEMENTS.items()
        ]

        super().__init__(
            placeholder=f"Choose achievement to {action}...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_use_achievement_action(interaction.user, self.action):
            if self.action == "give":
                return await interaction.response.send_message("❌ This is owner-only.", ephemeral=True)
            return await interaction.response.send_message("❌ You need **Manage Server** permission.", ephemeral=True)

        achievement_id = self.values[0]
        data = ACHIEVEMENTS[achievement_id]

        if self.action == "give":
            unlock_achievement(self.target.id, achievement_id)

            embed = discord.Embed(
                title="🏦 State Bank Achievement Granted",
                description=f"{self.target.mention} unlocked **{data['emoji']} {data['name']}**",
                color=rarity_color(data["rarity"])
            )
            embed.add_field(name="Description", value=data["description"], inline=False)
            embed.add_field(name="Rarity", value=data["rarity"], inline=True)

        else:
            remove_achievement(self.target.id, achievement_id)

            embed = discord.Embed(
                title="🏦 State Bank Achievement Removed",
                description=f"Removed **{data['emoji']} {data['name']}** from {self.target.mention}",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=None)


class AchievementAdminView(discord.ui.View):
    def __init__(self, target: discord.Member, action: str):
        super().__init__(timeout=120)
        self.add_item(AchievementSelect(target, action))


class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def build_achievements_embed(self, user: discord.Member):
        unlocked = get_user_achievements(user.id)
        unlocked_ids = [row[0] for row in unlocked]

        embed = discord.Embed(
            title="🏦 State Bank Achievements",
            description=f"Achievement profile for {user.mention}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        if not unlocked_ids:
            embed.add_field(
                name="No Achievements Yet",
                value="This user has not unlocked any State Bank achievements yet.",
                inline=False
            )
            return embed

        text = ""
        for achievement_id in unlocked_ids:
            data = ACHIEVEMENTS.get(achievement_id)

            if not data:
                text += f"❔ **Unknown Achievement**\n`{achievement_id}`\n\n"
                continue

            text += (
                f"{data['emoji']} **{data['name']}**\n"
                f"*{data['rarity']}* — {data['description']}\n"
                f"`{achievement_id}`\n\n"
            )

        embed.add_field(
            name=f"Unlocked: {len(unlocked_ids)}",
            value=text[:4000] if text else "No valid achievements found.",
            inline=False
        )

        return embed

    async def build_list_embed(self):
        embed = discord.Embed(
            title="📜 State Bank Achievement List",
            description="All available achievements and what they mean.",
            color=discord.Color.gold()
        )

        for achievement_id, data in ACHIEVEMENTS.items():
            embed.add_field(
                name=f"{data['emoji']} {data['name']} — {data['rarity']}",
                value=f"`{achievement_id}`\n{data['description']}",
                inline=False
            )

        return embed

    @app_commands.command(name="achievements", description="🏆 View State Bank achievements")
    async def achievements_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        user = member or interaction.user
        embed = await self.build_achievements_embed(user)
        await interaction.followup.send(embed=embed)

    @commands.command(name="achievements")
    async def achievements_prefix(self, ctx, member: discord.Member = None):
        user = member or ctx.author
        embed = await self.build_achievements_embed(user)
        await ctx.send(embed=embed)

    @app_commands.command(name="achievement-list", description="📜 View every State Bank achievement")
    async def achievement_list_slash(self, interaction: discord.Interaction):
        embed = await self.build_list_embed()
        await interaction.response.send_message(embed=embed)

    @commands.command(name="achlist")
    async def achievement_list_prefix(self, ctx):
        embed = await self.build_list_embed()
        await ctx.send(embed=embed)

    @app_commands.command(name="give-achievement", description="🏆 Owner only: give a user an achievement")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def give_achievement_slash(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ You cannot use this.", ephemeral=True)

        embed = discord.Embed(
            title="🏦 Give State Bank Achievement",
            description=f"Choose an achievement to give to {member.mention}.",
            color=discord.Color.gold()
        )

        await interaction.response.send_message(
            embed=embed,
            view=AchievementAdminView(member, "give"),
            ephemeral=True
        )

    @app_commands.command(name="remove-achievement", description="🗑️ Manager only: remove a user achievement")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def remove_achievement_slash(self, interaction: discord.Interaction, member: discord.Member):
        if not can_manage_server(interaction.user):
            return await interaction.response.send_message("❌ You need **Manage Server** permission.", ephemeral=True)

        embed = discord.Embed(
            title="🏦 Remove State Bank Achievement",
            description=f"Choose an achievement to remove from {member.mention}.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=AchievementAdminView(member, "remove"),
            ephemeral=True
        )

    @commands.command(name="giveach")
    async def give_achievement_prefix(self, ctx, member: discord.Member, achievement_id: str):
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ You cannot use this.")

        achievement_id = achievement_id.lower()

        if achievement_id not in ACHIEVEMENTS:
            return await ctx.send("❌ Invalid achievement ID. Use `!achlist` to see IDs.")

        unlock_achievement(member.id, achievement_id)
        data = ACHIEVEMENTS[achievement_id]

        await ctx.send(f"🏦 Gave **{data['emoji']} {data['name']}** to {member.mention}.")

    @commands.command(name="removeach")
    @commands.has_permissions(manage_guild=True)
    async def remove_achievement_prefix(self, ctx, member: discord.Member, achievement_id: str):
        if not can_manage_server(ctx.author):
            return await ctx.send("❌ You need **Manage Server** permission.")

        achievement_id = achievement_id.lower()

        if achievement_id not in ACHIEVEMENTS:
            return await ctx.send("❌ Invalid achievement ID. Use `!achlist` to see IDs.")

        remove_achievement(member.id, achievement_id)
        data = ACHIEVEMENTS[achievement_id]

        await ctx.send(f"🏦 Removed **{data['emoji']} {data['name']}** from {member.mention}.")


async def setup(bot):
    await bot.add_cog(Achievements(bot))
