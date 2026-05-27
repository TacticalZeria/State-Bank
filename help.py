
import discord
from discord.ext import commands
from discord import app_commands

BRAND = "State Bank"


def command_pair(slash: str, prefix: str, desc: str):
    return f"**`/{slash}`** / **`!{prefix}`**\n{desc}"


HELP_PAGES = {
    "overview": "Overview",
    "money": "Earning Money",
    "banking": "Banking",
    "games": "Games",
    "achievements": "Achievements",
    "collect": "Role Rewards",
    "profile": "Profiles",
    "allcommands": "All Commands",
    "support": "Support",
}


class HelpSelect(discord.ui.Select):
    def __init__(self, view_ref):
        self.view_ref = view_ref
        options = [
            discord.SelectOption(label="Overview", value="overview", emoji="🏦", description="Start here"),
            discord.SelectOption(label="Earning Money", value="money", emoji="💰", description="Work, crime, street, collect, rob"),
            discord.SelectOption(label="Banking", value="banking", emoji="🏛️", description="Wallet, bank, deposit, withdraw"),
            discord.SelectOption(label="Games", value="games", emoji="🎰", description="Casino and game commands"),
            discord.SelectOption(label="Achievements", value="achievements", emoji="🎖️", description="Achievement progress"),
            discord.SelectOption(label="Role Rewards", value="collect", emoji="🏷️", description="Collect rewards from roles"),
            discord.SelectOption(label="Profiles", value="profile", emoji="📊", description="Profile, balance, leaderboard"),
            discord.SelectOption(label="All Commands", value="allcommands", emoji="📚", description="All public commands"),
            discord.SelectOption(label="Support", value="support", emoji="🎫", description="How to get help"),
        ]
        super().__init__(placeholder="Choose a help category...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        await self.view_ref.show_page(interaction, self.values[0])


class HelpView(discord.ui.View):
    def __init__(self, user: discord.abc.User):
        super().__init__(timeout=240)
        self.user = user
        self.page = "overview"
        self.add_item(HelpSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Use `/help` to open your own help menu.", ephemeral=True)
            return False
        return True

    async def show_page(self, interaction: discord.Interaction, page: str):
        self.page = page
        await interaction.response.edit_message(embed=build_help_embed(interaction.user, page), view=self)

    @discord.ui.button(label="Back", emoji="⬅️", style=discord.ButtonStyle.gray, row=2)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pages = list(HELP_PAGES.keys())
        await self.show_page(interaction, pages[(pages.index(self.page) - 1) % len(pages)])

    @discord.ui.button(label="Home", emoji="🏦", style=discord.ButtonStyle.blurple, row=2)
    async def home_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_page(interaction, "overview")

    @discord.ui.button(label="Next", emoji="➡️", style=discord.ButtonStyle.gray, row=2)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pages = list(HELP_PAGES.keys())
        await self.show_page(interaction, pages[(pages.index(self.page) + 1) % len(pages)])

    @discord.ui.button(label="Close", emoji="🔒", style=discord.ButtonStyle.red, row=2)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception:
            try:
                await interaction.message.delete()
            except Exception:
                pass


def base_embed(user, title, description, color=discord.Color.gold()):
    embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"{BRAND} • Public Help Menu")
    return embed


def build_help_embed(user, page: str):
    page = page if page in HELP_PAGES else "overview"

    if page == "overview":
        embed = base_embed(user, "🏦 State Bank Help", (
            "**State Bank** is an economy, banking, casino, profile, achievement, and role reward bot.\n\n"
            "**Money examples:** `1000`, `1,000`, `10k`, `2.5m`, `1b`\n"
            "**Command styles:** slash commands use `/`, prefix commands use `!`"
        ))
        embed.add_field(name="Start Here", value=(
            "1. `/balance` or `!bal` — check your money.\n"
            "2. `/work`, `/crime`, or `/street` — earn coins.\n"
            "3. `/deposit` — store coins in your bank.\n"
            "4. `/slots`, `/blackjack`, `/roulette`, `/coinflip`, or `/mines` — play games.\n"
            "5. `/achievements` — view your progress."
        ), inline=False)
        embed.add_field(name="Tip", value="Most game commands use **wallet** coins. Bank coins are stored separately.", inline=False)
        return embed

    if page == "money":
        embed = base_embed(user, "💰 Earning Money", "Ways to earn, risk, and collect coins.", discord.Color.green())
        embed.add_field(name="Income Commands", value="\n\n".join([
            command_pair("work", "work", "Safe way to earn coins after a cooldown."),
            command_pair("street", "street", "Quick money command with smaller rewards."),
            command_pair("crime", "crime", "Risky money command. You can win or lose coins."),
            command_pair("collect", "collect", "Claim rewards from roles you have."),
        ]), inline=False)
        embed.add_field(name="Risk Command", value=command_pair("rob @user", "rob @user", "Attempt to rob another user. It can fail and has a cooldown."), inline=False)
        return embed

    if page == "banking":
        embed = base_embed(user, "🏛️ Banking", "Move coins between your wallet and bank.", discord.Color.blurple())
        embed.add_field(name="Wallet vs Bank", value="**Wallet** is spendable coins.\n**Bank** is stored coins.\n**Net Worth** is wallet + bank.", inline=False)
        embed.add_field(name="Deposit", value=command_pair("deposit amount", "dep amount", "Move wallet coins into your bank.") + "\n\nExamples: `/deposit 1,000`, `!dep 10k`, `/deposit all`", inline=False)
        embed.add_field(name="Withdraw", value=command_pair("withdraw amount", "with amount", "Move bank coins into your wallet.") + "\n\nExamples: `/withdraw 1,000`, `!with 10k`, `/withdraw all`", inline=False)
        return embed

    if page == "games":
        embed = base_embed(user, "🎰 Games", "Casino and game commands that use wallet coins.", discord.Color.purple())
        embed.add_field(name="Game Commands", value="\n\n".join([
            command_pair("slots bet", "slots bet", "Spin the slot machine."),
            command_pair("blackjack bet", "bj bet", "Play blackjack with buttons."),
            command_pair("roulette bet choice", "roulette bet choice", "Bet on red, black, green, odd, even, low, or high."),
            command_pair("coinflip @user bet choice", "cf @user bet choice", "Challenge another user to a coinflip."),
            command_pair("mines bet mines", "mines bet mines", "Reveal safe tiles and cash out before hitting a mine."),
            command_pair("mines-cancel", "minescancel", "Clear your stuck Mines game."),
        ]), inline=False)
        embed.add_field(name="Examples", value="`/slots 1,000`\n`!bj 2.5k`\n`/roulette 10k red`\n`/mines 5,000 3`", inline=False)
        embed.add_field(name="Reminder", value="Casino losses are normal. Confirmed bot errors can be reported to staff.", inline=False)
        return embed

    if page == "achievements":
        embed = base_embed(user, "🎖️ Achievements", "View your achievements and available achievement list.", discord.Color.teal())
        embed.add_field(name="Commands", value="\n\n".join([
            command_pair("achievements", "achievements", "View achievements you have unlocked."),
            command_pair("achievement-list", "achievementlist", "View achievements available in State Bank."),
        ]), inline=False)
        embed.add_field(name="What Achievements Are", value="Achievements are badges for progress, casino wins, economy milestones, and special events.", inline=False)
        return embed

    if page == "collect":
        embed = base_embed(user, "🏷️ Role Rewards", "Some servers give coin rewards to certain roles.", discord.Color.orange())
        embed.add_field(name="Commands", value="\n\n".join([
            command_pair("collect", "collect", "Claim coins from any reward roles you have."),
            command_pair("collect-list", "collectlist", "View role rewards available in this server."),
        ]), inline=False)
        embed.add_field(name="How It Works", value="Use `/collect-list` to see what rewards exist. Use `/collect` to claim ready rewards.", inline=False)
        return embed

    if page == "profile":
        embed = base_embed(user, "📊 Profiles & Stats", "View your money, stats, ranks, and progress.", discord.Color.blue())
        embed.add_field(name="Commands", value="\n\n".join([
            command_pair("balance", "bal", "View wallet, bank, net worth, wins, losses, and win rate."),
            command_pair("profile", "profile", "View your visual State Bank profile card."),
            command_pair("leaderboard", "lb", "View top players by net worth."),
            command_pair("achievements", "achievements", "View your achievement progress."),
        ]), inline=False)
        return embed

    if page == "allcommands":
        embed = base_embed(user, "📚 All Public Commands", "Every public State Bank command.", discord.Color.gold())
        embed.add_field(name="Money & Banking", value=(
            "`/balance` `!bal`\n`/profile` `!profile`\n`/leaderboard` `!lb`\n"
            "`/work` `!work`\n`/crime` `!crime`\n`/street` `!street`\n"
            "`/collect` `!collect`\n`/collect-list` `!collectlist`\n"
            "`/deposit` `!dep`\n`/withdraw` `!with`"
        ), inline=False)
        embed.add_field(name="Games", value=(
            "`/slots` `!slots`\n`/blackjack` `!bj`\n`/roulette` `!roulette`\n"
            "`/coinflip` `!cf`\n`/rob` `!rob`\n`/mines` `!mines`\n`/mines-cancel` `!minescancel`"
        ), inline=False)
        embed.add_field(name="Achievements & Help", value="`/achievements` `!achievements`\n`/achievement-list` `!achievementlist`\n`/help` `!help`\n`!commands`", inline=False)
        return embed

    if page == "support":
        embed = base_embed(user, "🎫 Support", "What to do if you need help.", discord.Color.magenta())
        embed.add_field(name="Need Help?", value="Use the support server ticket panel for setup questions, missing rewards, permission issues, bug reports, command errors, or general questions.", inline=False)
        embed.add_field(name="Bug Reports", value="Include what command you used, what happened, what you expected, and a screenshot if possible.", inline=False)
        return embed

    return base_embed(user, "🏦 State Bank Help", "Unknown help page.")


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_help(self, source, user):
        embed = build_help_embed(user, "overview")
        view = HelpView(user)

        if isinstance(source, discord.Interaction):
            await source.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await source.send(embed=embed, view=view)

    @app_commands.command(name="help", description="🏦 View the State Bank help menu")
    async def help_slash(self, interaction: discord.Interaction):
        await self.send_help(interaction, interaction.user)

    @commands.command(name="help")
    async def help_prefix(self, ctx):
        await self.send_help(ctx, ctx.author)

    @commands.command(name="commands")
    async def commands_prefix(self, ctx):
        await self.send_help(ctx, ctx.author)


async def setup(bot):
    await bot.add_cog(Help(bot))
