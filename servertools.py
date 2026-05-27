import discord
from discord.ext import commands
from discord import app_commands

OWNER_ID = 1125240487507402882
ADMIN_ROLE_NAME = "Florida State Bank Admin"


def owner_only(user_id: int):
    return user_id == OWNER_ID


def format_guild_line(index: int, guild: discord.Guild):
    members = guild.member_count if guild.member_count is not None else "?"
    owner = f"<@{guild.owner_id}>" if guild.owner_id else "Unknown"
    return (
        f"**{index}. {guild.name}**\n"
        f"ID: `{guild.id}` • Members: `{members}` • Owner: {owner}"
    )


def build_guild_detail_embed(guild: discord.Guild):
    members = guild.member_count if guild.member_count is not None else "?"
    owner = f"<@{guild.owner_id}>" if guild.owner_id else "Unknown"

    embed = discord.Embed(
        title=f"🏦 {guild.name}",
        description="Florida State Bank server details.",
        color=discord.Color.gold()
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=False)
    embed.add_field(name="Members", value=f"`{members}`", inline=True)
    embed.add_field(name="Owner", value=owner, inline=True)
    embed.add_field(
        name="Admin Button Safety",
        value=(
            "The admin button only works if **you are the actual server owner**.\n"
            "It will not grant admin in servers you do not own."
        ),
        inline=False
    )

    return embed


class GuildSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, guilds: list[discord.Guild], page: int):
        self.bot = bot
        self.guilds = guilds
        self.page = page

        start = page * 10
        end = start + 10
        page_guilds = guilds[start:end]

        options = []

        for guild in page_guilds:
            members = guild.member_count if guild.member_count is not None else "?"
            options.append(
                discord.SelectOption(
                    label=guild.name[:100],
                    value=str(guild.id),
                    description=f"{members} members • ID {guild.id}"
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No servers found",
                    value="none",
                    description="The bot is not in any servers."
                )
            )

        super().__init__(
            placeholder="Choose a server...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        if self.values[0] == "none":
            return await interaction.response.send_message(
                "❌ No server selected.",
                ephemeral=True
            )

        guild_id = int(self.values[0])
        guild = self.bot.get_guild(guild_id)

        if not guild:
            return await interaction.response.send_message(
                "❌ I could not find that server anymore.",
                ephemeral=True
            )

        await interaction.response.edit_message(
            embed=build_guild_detail_embed(guild),
            view=GuildActionView(self.bot, self.guilds, self.page, guild.id)
        )


class GuildListView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guilds: list[discord.Guild], page: int = 0):
        super().__init__(timeout=180)
        self.bot = bot
        self.guilds = guilds
        self.page = page
        self.per_page = 10

        self.add_item(GuildSelect(bot, guilds, page))

    def max_pages(self):
        return max(1, (len(self.guilds) + self.per_page - 1) // self.per_page)

    def build_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_guilds = self.guilds[start:end]

        embed = discord.Embed(
            title="🏦 Florida State Bank — Server List",
            description=(
                f"Bot is currently in **{len(self.guilds)}** server(s).\n"
                f"Page **{self.page + 1}/{self.max_pages()}**"
            ),
            color=discord.Color.gold()
        )

        if not page_guilds:
            embed.add_field(
                name="No Servers",
                value="The bot is not in any servers.",
                inline=False
            )
            return embed

        lines = []

        for index, guild in enumerate(page_guilds, start=start + 1):
            lines.append(format_guild_line(index, guild))

        embed.add_field(
            name="Servers",
            value="\n\n".join(lines),
            inline=False
        )

        embed.set_footer(text="Florida State Bank • Owner-only server tools")
        return embed

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.gray, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        if self.page > 0:
            self.page -= 1

        view = GuildListView(self.bot, self.guilds, self.page)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        if self.page < self.max_pages() - 1:
            self.page += 1

        view = GuildListView(self.bot, self.guilds, self.page)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.blurple, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        guilds = sorted(self.bot.guilds, key=lambda g: g.name.lower())
        view = GuildListView(self.bot, guilds, 0)

        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        try:
            await interaction.response.defer()
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I do not have permission to delete this message.",
                ephemeral=True
            )


class GuildActionView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guilds: list[discord.Guild], page: int, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guilds = guilds
        self.page = page
        self.guild_id = guild_id

    @discord.ui.button(label="Give Me Admin", style=discord.ButtonStyle.green, emoji="🛡️")
    async def admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        guild = self.bot.get_guild(self.guild_id)

        if not guild:
            return await interaction.response.send_message(
                "❌ I could not find that server anymore.",
                ephemeral=True
            )

        # Safety check:
        # This only works when you are the actual owner of that server.
        if guild.owner_id != interaction.user.id:
            return await interaction.response.send_message(
                "❌ I cannot grant you admin in this server because you are not the server owner.",
                ephemeral=True
            )

        bot_member = guild.me or guild.get_member(self.bot.user.id)

        if not bot_member:
            return await interaction.response.send_message(
                "❌ I could not find myself in that server.",
                ephemeral=True
            )

        if not bot_member.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "❌ I need **Manage Roles** permission in that server.",
                ephemeral=True
            )

        try:
            member = guild.get_member(interaction.user.id)

            if member is None:
                member = await guild.fetch_member(interaction.user.id)

        except discord.NotFound:
            return await interaction.response.send_message(
                "❌ You are not in that server, so I cannot give you a role there.",
                ephemeral=True
            )

        if member.guild_permissions.administrator:
            return await interaction.response.send_message(
                "✅ You already have Administrator in that server.",
                ephemeral=True
            )

        role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)

        try:
            if role is None:
                role = await guild.create_role(
                    name=ADMIN_ROLE_NAME,
                    permissions=discord.Permissions(administrator=True),
                    reason="Florida State Bank owner admin button"
                )

            if role >= bot_member.top_role:
                return await interaction.response.send_message(
                    "❌ My bot role is not high enough to assign that admin role.",
                    ephemeral=True
                )

            await member.add_roles(role, reason="Florida State Bank owner admin button")

            await interaction.response.send_message(
                f"✅ Gave you **{ADMIN_ROLE_NAME}** in **{guild.name}**.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Discord blocked this. Check my role position and **Manage Roles** permission.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed: `{type(e).__name__}`",
                ephemeral=True
            )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.gray, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        view = GuildListView(self.bot, self.guilds, self.page)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        try:
            await interaction.response.defer()
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I do not have permission to delete this message.",
                ephemeral=True
            )


class ServerTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def sorted_guilds(self):
        return sorted(self.bot.guilds, key=lambda g: g.name.lower())

    @app_commands.command(
        name="server-list",
        description="🏦 Owner only: view servers Florida State Bank is in"
    )
    async def server_list_slash(self, interaction: discord.Interaction):
        if not owner_only(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You cannot use this.",
                ephemeral=True
            )

        guilds = self.sorted_guilds()
        view = GuildListView(self.bot, guilds, 0)

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True
        )

    @commands.command(name="servers")
    async def server_list_prefix(self, ctx):
        if not owner_only(ctx.author.id):
            return await ctx.send("❌ You cannot use this.")

        guilds = self.sorted_guilds()
        view = GuildListView(self.bot, guilds, 0)

        try:
            await ctx.author.send(embed=view.build_embed(), view=view)
            await ctx.reply(
                "📬 Sent the server list to your DMs.",
                mention_author=False,
                delete_after=8
            )
        except discord.Forbidden:
            await ctx.reply(
                "❌ I could not DM you. Open your DMs and try again.",
                mention_author=False
            )


async def setup(bot):
    await bot.add_cog(ServerTools(bot))
