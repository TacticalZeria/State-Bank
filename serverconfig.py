import json
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

ANTIRAID_CONFIG_PATH = Path("data/antiraid.json")
UPDATE_WATCHER_STATE_PATH = Path("data/cog_update_state.json")
OWNER_ID = 1125240487507402882

PUBLIC_COMMANDS = {
    "balance", "profile", "leaderboard",
    "work", "crime", "street",
    "collect", "collect-list",
    "deposit", "withdraw",
    "slots", "blackjack", "roulette", "coinflip", "rob", "mines", "mines-cancel",
    "achievements", "achievement-list",
}

MANAGEMENT_COMMANDS = {
    "admin-panel",
    "give-achievement", "remove-achievement",
    "add-collect-role", "remove-collect-role",
    "server-list",
    "antiraid-enable", "antiraid-disable", "antiraid-status",
    "antiraid-whitelist", "antiraid-unwhitelist",
    "raid-lockdown", "raid-unlock",
    "server-config",
}

IMPORTANT_BOT_PERMS = [
    ("View Channels", "view_channel"),
    ("Send Messages", "send_messages"),
    ("Embed Links", "embed_links"),
    ("Attach Files", "attach_files"),
    ("Use External Emojis", "use_external_emojis"),
    ("Read Message History", "read_message_history"),
    ("Manage Roles", "manage_roles"),
    ("Manage Channels", "manage_channels"),
    ("Manage Messages", "manage_messages"),
    ("Moderate Members", "moderate_members"),
    ("Kick Members", "kick_members"),
    ("Ban Members", "ban_members"),
    ("Administrator", "administrator"),
]


def is_manager(member: discord.Member):
    return isinstance(member, discord.Member) and member.id == OWNER_ID


def yesno(value: bool):
    return "✅ Yes" if value else "❌ No"


def status_dot(value: bool):
    return "🟢" if value else "🔴"


def safe_percent(part: int, whole: int):
    if whole <= 0:
        return "0%"
    return f"{round((part / whole) * 100, 1)}%"


def read_json(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def short_list(lines, limit=15):
    if not lines:
        return "None"
    if len(lines) <= limit:
        return "\n".join(lines)
    shown = "\n".join(lines[:limit])
    return f"{shown}\n…and **{len(lines) - limit}** more."


def get_collect_rewards(guild_id: int):
    try:
        from database import get_collect_roles
        return get_collect_roles(guild_id)
    except Exception:
        return []


def get_economy_stats():
    try:
        from database import cursor
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(coins), 0), COALESCE(SUM(bank), 0) FROM economy")
        total_users, total_wallet, total_bank = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM user_achievements")
        total_achievements = cursor.fetchone()[0]

        return {
            "users": total_users or 0,
            "wallet": total_wallet or 0,
            "bank": total_bank or 0,
            "achievements": total_achievements or 0,
        }
    except Exception:
        return {
            "users": 0,
            "wallet": 0,
            "bank": 0,
            "achievements": 0,
        }


def fmt_money(amount: int):
    return f"{int(amount):,}"


class ServerConfigView(discord.ui.View):
    def __init__(self, cog, interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild = interaction.guild
        self.requester_id = interaction.user.id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id and not is_manager(interaction.user):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this panel.",
                ephemeral=True
            )
            return False
        return True

    async def update(self, interaction: discord.Interaction, page: str):
        embed = self.cog.build_embed(self.guild, page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Overview", emoji="🏦", style=discord.ButtonStyle.blurple, row=0)
    async def overview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "overview")

    @discord.ui.button(label="Permissions", emoji="🛡️", style=discord.ButtonStyle.gray, row=0)
    async def perms_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "permissions")

    @discord.ui.button(label="Economy", emoji="💰", style=discord.ButtonStyle.gray, row=0)
    async def economy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "economy")

    @discord.ui.button(label="Anti-Raid", emoji="🚨", style=discord.ButtonStyle.gray, row=1)
    async def antiraid_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "antiraid")

    @discord.ui.button(label="Commands", emoji="⌨️", style=discord.ButtonStyle.gray, row=1)
    async def commands_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "commands")

    @discord.ui.button(label="Health Check", emoji="📡", style=discord.ButtonStyle.green, row=1)
    async def health_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update(interaction, "health")

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


class ServerConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def bot_member(self, guild: discord.Guild):
        return guild.me or guild.get_member(self.bot.user.id)

    def build_embed(self, guild: discord.Guild, page: str):
        builders = {
            "overview": self.overview_embed,
            "permissions": self.permissions_embed,
            "economy": self.economy_embed,
            "antiraid": self.antiraid_embed,
            "commands": self.commands_embed,
            "health": self.health_embed,
        }
        return builders.get(page, self.overview_embed)(guild)

    def base_embed(self, guild: discord.Guild, title: str, description: str, color=discord.Color.gold()):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(text="State Bank • Server Config")
        return embed

    def overview_embed(self, guild: discord.Guild):
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])

        embed = self.base_embed(
            guild,
            "🏦 State Bank Server Configuration",
            "Full server setup overview for State Bank.",
            discord.Color.gold()
        )

        embed.add_field(
            name="Server",
            value=(
                f"**Name:** {guild.name}\n"
                f"**ID:** `{guild.id}`\n"
                f"**Owner:** <@{guild.owner_id}>\n"
                f"**Created:** <t:{int(guild.created_at.timestamp())}:D>"
            ),
            inline=False
        )

        embed.add_field(
            name="Population",
            value=(
                f"👥 Members: **{guild.member_count or 0}**\n"
                f"🙂 Humans: **{humans}**\n"
                f"🤖 Bots: **{bots}**"
            ),
            inline=True
        )

        embed.add_field(
            name="Structure",
            value=(
                f"📁 Categories: **{len(guild.categories)}**\n"
                f"💬 Text Channels: **{len(guild.text_channels)}**\n"
                f"🔊 Voice Channels: **{len(guild.voice_channels)}**"
            ),
            inline=True
        )

        embed.add_field(
            name="Server Assets",
            value=(
                f"🎭 Roles: **{len(guild.roles)}**\n"
                f"😀 Emojis: **{len(guild.emojis)}**\n"
                f"🔐 Verification: **{str(guild.verification_level).title()}**"
            ),
            inline=True
        )

        embed.add_field(name="Quick Rating", value=self.quick_rating(guild), inline=False)
        return embed

    def quick_rating(self, guild: discord.Guild):
        bot_member = self.bot_member(guild)
        perms = bot_member.guild_permissions if bot_member else discord.Permissions.none()

        checks = [
            ("Bot can send messages", perms.send_messages),
            ("Bot can embed links", perms.embed_links),
            ("Bot can attach images", perms.attach_files),
            ("Bot can manage roles", perms.manage_roles),
            ("Bot can moderate members", perms.moderate_members),
            ("Server has verification enabled", str(guild.verification_level) != "none"),
            ("Server has roles", len(guild.roles) > 1),
            ("Server has channels", len(guild.text_channels) > 0),
        ]

        passed = sum(1 for _, ok in checks if ok)
        lines = [f"{status_dot(ok)} {name}" for name, ok in checks]

        return f"**Setup Score:** `{passed}/{len(checks)}`\n" + "\n".join(lines)

    def permissions_embed(self, guild: discord.Guild):
        bot_member = self.bot_member(guild)
        perms = bot_member.guild_permissions if bot_member else discord.Permissions.none()

        embed = self.base_embed(
            guild,
            "🛡️ State Bank Permission Audit",
            "Checks the bot's important permissions in this server.",
            discord.Color.blurple()
        )

        perm_lines = []
        missing_lines = []

        for nice_name, attr in IMPORTANT_BOT_PERMS:
            has_perm = getattr(perms, attr, False)
            perm_lines.append(f"{status_dot(has_perm)} **{nice_name}**")

            if attr in {"send_messages", "embed_links", "attach_files", "read_message_history"} and not has_perm:
                missing_lines.append(nice_name)

        embed.add_field(name="Bot Permissions", value=short_list(perm_lines, limit=20), inline=False)

        if missing_lines:
            embed.add_field(
                name="Important Missing Permissions",
                value="\n".join(f"❌ {name}" for name in missing_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="Important Missing Permissions",
                value="✅ No critical message/embed permissions are missing.",
                inline=False
            )

        top_role = bot_member.top_role.mention if bot_member and bot_member.top_role else "Unknown"
        embed.add_field(
            name="Role Position",
            value=(
                f"**Bot Top Role:** {top_role}\n"
                "If State Bank gives/removes roles later, its role must be above those roles."
            ),
            inline=False
        )

        return embed

    def economy_embed(self, guild: discord.Guild):
        rewards = get_collect_rewards(guild.id)
        stats = get_economy_stats()

        embed = self.base_embed(
            guild,
            "💰 State Bank Economy Configuration",
            "Economy, banking, achievements, and role collect setup.",
            discord.Color.green()
        )

        embed.add_field(
            name="Global Economy Database",
            value=(
                f"👤 Economy Users: **{stats['users']:,}**\n"
                f"💵 Total Wallet Coins: **{fmt_money(stats['wallet'])}**\n"
                f"🏦 Total Bank Coins: **{fmt_money(stats['bank'])}**\n"
                f"🎖️ Achievement Unlocks: **{stats['achievements']:,}**"
            ),
            inline=False
        )

        if rewards:
            lines = []
            for role_id, amount, cooldown in rewards:
                role = guild.get_role(role_id)
                role_text = role.mention if role else f"`Missing Role {role_id}`"
                minutes = int(cooldown // 60)
                lines.append(f"🏷️ {role_text} → **{amount:,} Coins** every **{minutes}m**")

            embed.add_field(name=f"Role Collect Rewards ({len(rewards)})", value=short_list(lines, limit=15), inline=False)
        else:
            embed.add_field(
                name="Role Collect Rewards",
                value="❌ No collect rewards are set up.\nUse `!addcollectrole @role amount cooldown_minutes`.",
                inline=False
            )

        embed.add_field(
            name="Public Economy Commands",
            value=(
                "`/balance` `/profile` `/leaderboard`\n"
                "`/work` `/crime` `/street`\n"
                "`/collect` `/collect-list`\n"
                "`/deposit` `/withdraw`"
            ),
            inline=False
        )

        return embed

    def antiraid_embed(self, guild: discord.Guild):
        data = read_json(ANTIRAID_CONFIG_PATH, {})
        config = data.get(str(guild.id), {})

        embed = self.base_embed(
            guild,
            "🚨 State Bank Anti-Raid Configuration",
            "Anti-raid, lockdown, spam protection, and whitelist status.",
            discord.Color.red()
        )

        if not config:
            embed.add_field(name="Status", value="❌ No anti-raid config found for this server yet.", inline=False)
            embed.add_field(name="Setup", value="Use `!antiraid enable` if this server needs protection.", inline=False)
            return embed

        log_channel = guild.get_channel(config.get("log_channel_id")) if config.get("log_channel_id") else None
        whitelist_ids = config.get("whitelist_role_ids", [])
        whitelist_roles = []

        for role_id in whitelist_ids:
            role = guild.get_role(role_id)
            whitelist_roles.append(role.mention if role else f"`Missing Role {role_id}`")

        embed.add_field(
            name="Core Status",
            value=(
                f"Enabled: **{yesno(config.get('enabled', False))}**\n"
                f"Lockdown Active: **{yesno(config.get('lockdown', False))}**\n"
                f"Auto Kick: **{yesno(config.get('auto_kick', False))}**\n"
                f"Log Channel: {log_channel.mention if log_channel else 'None'}"
            ),
            inline=False
        )

        embed.add_field(
            name="Join Protection",
            value=(
                f"Account Age Gate: **{int(config.get('account_age_seconds', 0) // 60)}m**\n"
                f"Join Trigger: **{config.get('join_limit', 0)} joins / {config.get('join_window_seconds', 0)}s**"
            ),
            inline=True
        )

        embed.add_field(
            name="Message Protection",
            value=(
                f"Message Spam: **{config.get('message_limit', 0)} msgs / {config.get('message_window_seconds', 0)}s**\n"
                f"Mention Limit: **{config.get('mention_limit', 0)} mentions**"
            ),
            inline=True
        )

        embed.add_field(name="Whitelisted Roles", value=short_list(whitelist_roles, limit=10), inline=False)
        return embed

    def commands_embed(self, guild: discord.Guild):
        names = sorted(cmd.name for cmd in self.bot.tree.get_commands())

        public = [f"`/{name}`" for name in names if name in PUBLIC_COMMANDS]
        management = [f"`/{name}`" for name in names if name in MANAGEMENT_COMMANDS]
        extra = [f"`/{name}`" for name in names if name not in PUBLIC_COMMANDS and name not in MANAGEMENT_COMMANDS]

        embed = self.base_embed(
            guild,
            "⌨️ State Bank Command Configuration",
            "Slash command visibility and category audit.",
            discord.Color.purple()
        )

        embed.add_field(name=f"Public Commands ({len(public)})", value=short_list(public, limit=25), inline=False)
        embed.add_field(name=f"Manager / Owner Commands ({len(management)})", value=short_list(management, limit=20), inline=False)
        embed.add_field(name=f"Extra Commands ({len(extra)})", value=short_list(extra, limit=20), inline=False)

        embed.add_field(
            name="Prefix Commands To Remember",
            value=(
                "`!ap` owner panel\n"
                "`!updatepanel` update log panel\n"
                "`!addcollectrole` role collect setup\n"
                "`!antiraid enable` anti-raid setup\n"
                "`!raidlock` emergency lockdown"
            ),
            inline=False
        )

        return embed

    def health_embed(self, guild: discord.Guild):
        bot_member = self.bot_member(guild)
        perms = bot_member.guild_permissions if bot_member else discord.Permissions.none()
        rewards = get_collect_rewards(guild.id)
        antiraid_data = read_json(ANTIRAID_CONFIG_PATH, {})
        antiraid_config = antiraid_data.get(str(guild.id), {})
        update_state_exists = UPDATE_WATCHER_STATE_PATH.exists()

        checks = [
            ("Bot is in server cache", bot_member is not None),
            ("Can send messages", perms.send_messages),
            ("Can embed links", perms.embed_links),
            ("Can attach files", perms.attach_files),
            ("Can read message history", perms.read_message_history),
            ("Manage Roles available", perms.manage_roles),
            ("Manage Channels available", perms.manage_channels),
            ("Moderate Members available", perms.moderate_members),
            ("Collect rewards configured", bool(rewards)),
            ("Anti-raid config exists", bool(antiraid_config)),
            ("Update watcher baseline exists", update_state_exists),
            ("Slash commands loaded", len(self.bot.tree.get_commands()) > 0),
        ]

        passed = sum(1 for _, ok in checks if ok)
        total = len(checks)

        embed = self.base_embed(
            guild,
            "📡 State Bank Health Check",
            "Detailed bot/server readiness report.",
            discord.Color.teal()
        )

        embed.add_field(name="Overall Health", value=f"**{passed}/{total} checks passed** — `{safe_percent(passed, total)}`", inline=False)
        embed.add_field(name="Checks", value="\n".join(f"{status_dot(ok)} {name}" for name, ok in checks), inline=False)

        recommendations = []
        if not perms.embed_links:
            recommendations.append("Give State Bank **Embed Links** permission.")
        if not perms.attach_files:
            recommendations.append("Give State Bank **Attach Files** permission for Pillow images.")
        if not perms.manage_roles:
            recommendations.append("Give State Bank **Manage Roles** only if you need role rewards later.")
        if not rewards:
            recommendations.append("Set up role collect rewards with `!addcollectrole`.")
        if not antiraid_config:
            recommendations.append("Configure anti-raid if this server needs protection.")
        if not update_state_exists:
            recommendations.append("Run the update watcher once so it can create its baseline.")

        embed.add_field(
            name="Recommendations",
            value=short_list([f"• {item}" for item in recommendations], limit=10) if recommendations else "✅ No major recommendations.",
            inline=False
        )

        return embed

    @app_commands.command(name="server-config", description="🏦 View detailed State Bank server configuration")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def server_config_slash(self, interaction: discord.Interaction):
        if not is_manager(interaction.user):
            return await interaction.response.send_message("❌ You need **Manage Server** permission to use this.", ephemeral=True)

        view = ServerConfigView(self, interaction)
        embed = self.build_embed(interaction.guild, "overview")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.command(name="serverconfig")
    async def server_config_prefix(self, ctx):
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ This command is owner-only.")

        fake_interaction = type("FakeInteraction", (), {"guild": ctx.guild, "user": ctx.author})
        view = ServerConfigView(self, fake_interaction)
        embed = self.build_embed(ctx.guild, "overview")
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(ServerConfig(bot))
