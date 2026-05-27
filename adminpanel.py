import discord
from discord.ext import commands

from database import (
    add_coins,
    remove_coins,
    get_coins,
    unlock_achievement,
    remove_achievement as db_remove_achievement,
    get_user_achievements
)

OWNER_ID = 1125240487507402882

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
    "casino_elite": {"name": "Casino Elite", "emoji": "👑", "rarity": "Mythic", "description": "Reserved for the most dominant players in the economy."},
}



def is_owner(user):
    return user.id == OWNER_ID


async def deny(interaction: discord.Interaction):
    await interaction.response.send_message(
        "❌ This panel is owner-only.",
        ephemeral=True
    )


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


class AmountModal(discord.ui.Modal):
    def __init__(self, action: str, member: discord.Member):
        super().__init__(title=f"{action.title()} Coins")
        self.action = action
        self.member = member
        self.amount = discord.ui.TextInput(label="Amount", placeholder="Example: 5000", required=True)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_owner(interaction.user):
            return await deny(interaction)

        try:
            amount = int(self.amount.value)
            if amount <= 0:
                return await interaction.response.send_message("❌ Amount must be above 0.", ephemeral=True)

            if self.action == "give":
                add_coins(self.member.id, amount)
                title = "🏦 Coins Given"
                desc = f"Gave **{amount:,} Coins** to {self.member.mention}"
                color = discord.Color.green()
            else:
                remove_coins(self.member.id, amount)
                title = "🏦 Coins Removed"
                desc = f"Removed **{amount:,} Coins** from {self.member.mention}"
                color = discord.Color.red()

            embed = discord.Embed(title=title, description=desc, color=color)
            embed.add_field(name="New Wallet", value=f"{get_coins(self.member.id):,} Coins", inline=False)
            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message("❌ Enter a valid number.", ephemeral=True)


class CoinMemberSelect(discord.ui.UserSelect):
    def __init__(self, action: str):
        self.action = action
        super().__init__(placeholder="Choose a member...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction.user):
            return await deny(interaction)

        member = self.values[0]

        if self.action in ["give", "remove"]:
            return await interaction.response.send_modal(AmountModal(self.action, member))

        embed = discord.Embed(
            title="🏦 User Wallet",
            description=f"{member.mention} has **{get_coins(member.id):,} Coins**",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class AchievementMemberSelect(discord.ui.UserSelect):
    def __init__(self, action: str):
        self.action = action
        super().__init__(placeholder="Choose a member...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction.user):
            return await deny(interaction)

        member = self.values[0]

        if self.action in ["give", "remove"]:
            return await interaction.response.edit_message(
                content=f"Choose an achievement for {member.mention}:",
                embed=None,
                view=AchievementSelectView(member, self.action)
            )

        rows = get_user_achievements(member.id)
        ids = [row[0] for row in rows]

        embed = discord.Embed(
            title="🏦 User Achievements",
            description=f"Achievements for {member.mention}",
            color=discord.Color.gold()
        )

        if not ids:
            embed.add_field(name="None", value="This user has no achievements.", inline=False)
        else:
            text = ""
            for ach_id in ids:
                data = ACHIEVEMENTS.get(ach_id)
                if data:
                    text += f"{data['emoji']} **{data['name']}** — *{data['rarity']}*\n{data['description']}\n\n"
                else:
                    text += f"❔ Unknown — `{ach_id}`\n"
            embed.add_field(name=f"Unlocked: {len(ids)}", value=text[:4000], inline=False)

        await interaction.response.edit_message(content=None, embed=embed, view=None)


class AchievementSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, action: str):
        self.member = member
        self.action = action
        options = [
            discord.SelectOption(
                label=data["name"],
                value=ach_id,
                emoji=data["emoji"],
                description=data["rarity"]
            )
            for ach_id, data in ACHIEVEMENTS.items()
        ]
        super().__init__(placeholder="Choose an achievement...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction.user):
            return await deny(interaction)

        ach_id = self.values[0]
        data = ACHIEVEMENTS[ach_id]

        if self.action == "give":
            unlock_achievement(self.member.id, ach_id)
            embed = discord.Embed(
                title="🏦 Achievement Given",
                description=f"{self.member.mention} unlocked **{data['emoji']} {data['name']}**",
                color=rarity_color(data["rarity"])
            )
            embed.add_field(name="Description", value=data["description"], inline=False)
            embed.add_field(name="Rarity", value=data["rarity"], inline=True)
        else:
            db_remove_achievement(self.member.id, ach_id)
            embed = discord.Embed(
                title="🏦 Achievement Removed",
                description=f"Removed **{data['emoji']} {data['name']}** from {self.member.mention}",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(content=None, embed=embed, view=None)


class CoinSelectView(discord.ui.View):
    def __init__(self, action: str):
        super().__init__(timeout=120)
        self.add_item(CoinMemberSelect(action))


class AchievementMemberView(discord.ui.View):
    def __init__(self, action: str):
        super().__init__(timeout=120)
        self.add_item(AchievementMemberSelect(action))


class AchievementSelectView(discord.ui.View):
    def __init__(self, member: discord.Member, action: str):
        super().__init__(timeout=120)
        self.add_item(AchievementSelect(member, action))


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Give Coins", style=discord.ButtonStyle.green, emoji="💰", row=0)
    async def give_coins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner(interaction.user):
            return await deny(interaction)
        await interaction.response.send_message("Choose a member to give coins to:", view=CoinSelectView("give"))

    @discord.ui.button(label="Remove Coins", style=discord.ButtonStyle.red, emoji="💸", row=0)
    async def remove_coins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner(interaction.user):
            return await deny(interaction)
        await interaction.response.send_message("Choose a member to remove coins from:", view=CoinSelectView("remove"))

    @discord.ui.button(label="Check Balance", style=discord.ButtonStyle.blurple, emoji="📊", row=0)
    async def check_balance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner(interaction.user):
            return await deny(interaction)
        await interaction.response.send_message("Choose a member to check:", view=CoinSelectView("balance"))

    @discord.ui.button(label="Give Achievement", style=discord.ButtonStyle.green, emoji="🏆", row=1)
    async def give_achievement_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner(interaction.user):
            return await deny(interaction)
        await interaction.response.send_message("Choose a member:", view=AchievementMemberView("give"))

    @discord.ui.button(label="Remove Achievement", style=discord.ButtonStyle.red, emoji="🗑️", row=1)
    async def remove_achievement_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner(interaction.user):
            return await deny(interaction)
        await interaction.response.send_message("Choose a member:", view=AchievementMemberView("remove"))

    @discord.ui.button(label="Check Achievements", style=discord.ButtonStyle.gray, emoji="🎖️", row=1)
    async def check_achievements_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner(interaction.user):
            return await deny(interaction)
        await interaction.response.send_message("Choose a member:", view=AchievementMemberView("check"))

    @discord.ui.button(label="Close", style=discord.ButtonStyle.gray, emoji="🔒", row=2)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner(interaction.user):
            return await deny(interaction)
        try:
            await interaction.response.defer()
            await interaction.message.delete()
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete this message.", ephemeral=True)
        except discord.NotFound:
            pass


class AdminPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def build_panel_embed(self):
        embed = discord.Embed(
            title="🏦 State Bank Admin Panel",
            description="Owner-only economy and achievement controls.",
            color=discord.Color.purple()
        )
        embed.add_field(name="Economy", value="💰 Give Coins\n💸 Remove Coins\n📊 Check Balance", inline=True)
        embed.add_field(name="Achievements", value="🏆 Give Achievement\n🗑️ Remove Achievement\n🎖️ Check Achievements", inline=True)
        embed.add_field(name="Access", value="Only the bot owner ID can use this panel.", inline=False)
        embed.set_footer(text="State Bank • Owner Panel")
        return embed

    @discord.app_commands.command(name="admin-panel", description="🏦 Owner-only admin panel")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def admin_panel_slash(self, interaction: discord.Interaction):
        if not is_owner(interaction.user):
            return await interaction.response.send_message("❌ This panel is owner-only.", ephemeral=True)

        await interaction.response.send_message(embed=self.build_panel_embed(), view=AdminPanelView(), ephemeral=True)

    @commands.command(name="ap")
    async def admin_panel_prefix(self, ctx):
        if not is_owner(ctx.author):
            return await ctx.send("❌ This panel is owner-only.")

        await ctx.send(embed=self.build_panel_embed(), view=AdminPanelView())


async def setup(bot):
    await bot.add_cog(AdminPanel(bot))
