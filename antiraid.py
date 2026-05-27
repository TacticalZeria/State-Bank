import json
import time
import datetime
from pathlib import Path
from collections import defaultdict, deque

import discord
from discord.ext import commands
from discord import app_commands

OWNER_ID = 1125240487507402882
CONFIG_PATH = Path("data/antiraid.json")

DEFAULT_CONFIG = {
    "enabled": False,
    "log_channel_id": None,
    "auto_kick": False,
    "account_age_seconds": 3600,
    "join_limit": 8,
    "join_window_seconds": 20,
    "message_limit": 6,
    "message_window_seconds": 8,
    "mention_limit": 8,
    "lockdown": False,
    "locked_channel_ids": [],
    "whitelist_role_ids": []
}


def format_seconds(seconds: int):
    seconds = max(0, int(seconds))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def is_owner_or_admin(member: discord.Member):
    if member.id == OWNER_ID:
        return True
    if member.guild_permissions.administrator:
        return True
    if member.guild_permissions.manage_guild:
        return True
    return False


class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.configs = self.load_configs()
        self.join_cache = defaultdict(deque)
        self.message_cache = defaultdict(lambda: defaultdict(deque))

    # =========================
    # CONFIG
    # =========================

    def load_configs(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            CONFIG_PATH.write_text("{}", encoding="utf-8")
            return {}
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_configs(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self.configs, indent=4), encoding="utf-8")

    def get_config(self, guild_id: int):
        gid = str(guild_id)
        if gid not in self.configs:
            self.configs[gid] = DEFAULT_CONFIG.copy()
            self.save_configs()

        config = DEFAULT_CONFIG.copy()
        config.update(self.configs.get(gid, {}))
        self.configs[gid] = config
        return config

    def update_config(self, guild_id: int, **kwargs):
        config = self.get_config(guild_id)
        config.update(kwargs)
        self.configs[str(guild_id)] = config
        self.save_configs()
        return config

    async def send_log(self, guild: discord.Guild, title: str, description: str, color=discord.Color.orange()):
        config = self.get_config(guild.id)
        channel_id = config.get("log_channel_id")
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_footer(text="State Bank • Anti-Raid")

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    def is_whitelisted(self, member: discord.Member):
        config = self.get_config(member.guild.id)
        whitelist = set(config.get("whitelist_role_ids", []))
        member_roles = {role.id for role in member.roles}
        return bool(whitelist & member_roles)

    async def timeout_member(self, member: discord.Member, minutes: int, reason: str):
        try:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
            await member.timeout(until, reason=reason)
            return True
        except Exception:
            return False

    async def safe_delete(self, message: discord.Message):
        try:
            await message.delete()
        except Exception:
            pass

    # =========================
    # LOCKDOWN
    # =========================

    async def lockdown_guild(self, guild: discord.Guild, reason: str = "Anti-raid lockdown"):
        config = self.get_config(guild.id)
        if config.get("lockdown"):
            return False, "Server is already locked down."

        locked = []
        default_role = guild.default_role

        for channel in guild.text_channels:
            try:
                overwrites = channel.overwrites_for(default_role)
                if overwrites.send_messages is False:
                    continue
                overwrites.send_messages = False
                await channel.set_permissions(default_role, overwrite=overwrites, reason=reason)
                locked.append(channel.id)
            except Exception:
                continue

        self.update_config(guild.id, lockdown=True, locked_channel_ids=locked)
        await self.send_log(guild, "🚨 Anti-Raid Lockdown Enabled", f"Locked **{len(locked)}** text channel(s).\nReason: {reason}", discord.Color.red())
        return True, f"Locked **{len(locked)}** text channel(s)."

    async def unlock_guild(self, guild: discord.Guild, reason: str = "Anti-raid unlock"):
        config = self.get_config(guild.id)
        if not config.get("lockdown"):
            return False, "Server is not locked down."

        unlocked = 0
        default_role = guild.default_role

        for channel_id in config.get("locked_channel_ids", []):
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            try:
                overwrites = channel.overwrites_for(default_role)
                overwrites.send_messages = None
                await channel.set_permissions(default_role, overwrite=overwrites, reason=reason)
                unlocked += 1
            except Exception:
                continue

        self.update_config(guild.id, lockdown=False, locked_channel_ids=[])
        await self.send_log(guild, "✅ Anti-Raid Lockdown Disabled", f"Unlocked **{unlocked}** text channel(s).\nReason: {reason}", discord.Color.green())
        return True, f"Unlocked **{unlocked}** text channel(s)."

    # =========================
    # EVENTS
    # =========================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.guild:
            return

        config = self.get_config(member.guild.id)
        if not config.get("enabled"):
            return

        guild = member.guild
        current = time.time()

        # Young account gate
        account_age = current - member.created_at.timestamp()
        if account_age < config.get("account_age_seconds", 3600):
            await self.send_log(
                guild,
                "⚠️ New Account Joined",
                f"{member.mention} joined with a young account.\nAccount Age: **{format_seconds(account_age)}**",
                discord.Color.orange()
            )

            if config.get("auto_kick"):
                try:
                    await member.kick(reason="State Bank anti-raid: new account gate")
                    await self.send_log(guild, "🚨 Member Auto-Kicked", f"Kicked {member.mention} for young account age.", discord.Color.red())
                except Exception:
                    pass

        # Join burst detection
        joins = self.join_cache[guild.id]
        joins.append(current)
        window = config.get("join_window_seconds", 20)

        while joins and current - joins[0] > window:
            joins.popleft()

        if len(joins) >= config.get("join_limit", 8):
            await self.send_log(
                guild,
                "🚨 Join Raid Detected",
                f"Detected **{len(joins)}** joins within **{window}s**. Attempting lockdown.",
                discord.Color.red()
            )
            await self.lockdown_guild(guild, reason="Join raid detected")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        config = self.get_config(message.guild.id)
        if not config.get("enabled"):
            return

        if not isinstance(message.author, discord.Member):
            return

        if self.is_whitelisted(message.author):
            return

        guild_id = message.guild.id
        user_id = message.author.id
        current = time.time()

        timestamps = self.message_cache[guild_id][user_id]
        timestamps.append(current)
        window = config.get("message_window_seconds", 8)

        while timestamps and current - timestamps[0] > window:
            timestamps.popleft()

        mention_count = len(message.mentions) + len(message.role_mentions)
        if mention_count >= config.get("mention_limit", 8):
            await self.safe_delete(message)
            await self.timeout_member(message.author, 10, "State Bank anti-raid: mention spam")
            await self.send_log(
                message.guild,
                "🚨 Mention Spam Blocked",
                f"{message.author.mention} sent **{mention_count}** mentions.\nMessage deleted and user timed out.",
                discord.Color.red()
            )
            return

        if len(timestamps) >= config.get("message_limit", 6):
            await self.safe_delete(message)
            await self.timeout_member(message.author, 5, "State Bank anti-raid: message spam")
            await self.send_log(
                message.guild,
                "🚨 Message Spam Blocked",
                f"{message.author.mention} sent **{len(timestamps)}** messages in **{window}s**.\nMessage deleted and user timed out.",
                discord.Color.red()
            )
            timestamps.clear()

    # =========================
    # COMMAND HELPERS
    # =========================

    async def require_mod(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return False

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return False

        if not is_owner_or_admin(interaction.user):
            await interaction.response.send_message("❌ You need Administrator or Manage Server to use this.", ephemeral=True)
            return False

        return True

    # =========================
    # SLASH COMMANDS
    # =========================

    @app_commands.command(name="antiraid-enable", description="🛡️ Enable State Bank anti-raid protection")
    @app_commands.describe(
        log_channel="Channel where anti-raid logs are sent",
        auto_kick="Kick accounts under the account age gate",
        account_age_minutes="Minimum account age in minutes",
        join_limit="How many joins trigger lockdown",
        join_window_seconds="Time window for join raid detection"
    )
    async def antiraid_enable(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel = None,
        auto_kick: bool = False,
        account_age_minutes: int = 60,
        join_limit: int = 8,
        join_window_seconds: int = 20
    ):
        if not await self.require_mod(interaction):
            return

        if account_age_minutes < 0:
            return await interaction.response.send_message("❌ Account age minutes cannot be negative.", ephemeral=True)
        if join_limit < 2:
            return await interaction.response.send_message("❌ Join limit must be at least 2.", ephemeral=True)
        if join_window_seconds < 5:
            return await interaction.response.send_message("❌ Join window must be at least 5 seconds.", ephemeral=True)

        self.update_config(
            interaction.guild.id,
            enabled=True,
            log_channel_id=log_channel.id if log_channel else None,
            auto_kick=auto_kick,
            account_age_seconds=account_age_minutes * 60,
            join_limit=join_limit,
            join_window_seconds=join_window_seconds
        )

        embed = discord.Embed(
            title="🛡️ Anti-Raid Enabled",
            description="State Bank anti-raid protection is now active.",
            color=discord.Color.green()
        )
        embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "None", inline=True)
        embed.add_field(name="Auto Kick", value=str(auto_kick), inline=True)
        embed.add_field(name="Account Age Gate", value=f"{account_age_minutes} minutes", inline=True)
        embed.add_field(name="Join Raid Trigger", value=f"{join_limit} joins / {join_window_seconds}s", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="antiraid-disable", description="🛡️ Disable State Bank anti-raid protection")
    async def antiraid_disable(self, interaction: discord.Interaction):
        if not await self.require_mod(interaction):
            return
        self.update_config(interaction.guild.id, enabled=False)
        await interaction.response.send_message("🛡️ State Bank anti-raid protection is now **disabled**.")

    @app_commands.command(name="antiraid-status", description="🛡️ View anti-raid settings")
    async def antiraid_status(self, interaction: discord.Interaction):
        if not await self.require_mod(interaction):
            return

        config = self.get_config(interaction.guild.id)
        log_channel = interaction.guild.get_channel(config.get("log_channel_id")) if config.get("log_channel_id") else None

        embed = discord.Embed(title="🛡️ State Bank Anti-Raid Status", color=discord.Color.gold())
        embed.add_field(name="Enabled", value=str(config.get("enabled")), inline=True)
        embed.add_field(name="Auto Kick", value=str(config.get("auto_kick")), inline=True)
        embed.add_field(name="Lockdown", value=str(config.get("lockdown")), inline=True)
        embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "None", inline=False)
        embed.add_field(name="Account Age Gate", value=format_seconds(config.get("account_age_seconds")), inline=True)
        embed.add_field(name="Join Raid Trigger", value=f"{config.get('join_limit')} joins / {config.get('join_window_seconds')}s", inline=True)
        embed.add_field(name="Spam Trigger", value=f"{config.get('message_limit')} msgs / {config.get('message_window_seconds')}s", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="raid-lockdown", description="🚨 Manually lock all text channels")
    async def raid_lockdown(self, interaction: discord.Interaction, reason: str = "Manual lockdown"):
        if not await self.require_mod(interaction):
            return
        await interaction.response.defer()
        success, msg = await self.lockdown_guild(interaction.guild, reason=reason)
        color = discord.Color.red() if success else discord.Color.orange()
        await interaction.followup.send(embed=discord.Embed(title="🚨 Raid Lockdown", description=msg, color=color))

    @app_commands.command(name="raid-unlock", description="✅ Unlock channels locked by raid lockdown")
    async def raid_unlock(self, interaction: discord.Interaction, reason: str = "Manual unlock"):
        if not await self.require_mod(interaction):
            return
        await interaction.response.defer()
        success, msg = await self.unlock_guild(interaction.guild, reason=reason)
        color = discord.Color.green() if success else discord.Color.orange()
        await interaction.followup.send(embed=discord.Embed(title="✅ Raid Unlock", description=msg, color=color))

    @app_commands.command(name="antiraid-whitelist", description="✅ Ignore a role from anti-spam checks")
    async def antiraid_whitelist(self, interaction: discord.Interaction, role: discord.Role):
        if not await self.require_mod(interaction):
            return
        config = self.get_config(interaction.guild.id)
        whitelist = set(config.get("whitelist_role_ids", []))
        whitelist.add(role.id)
        self.update_config(interaction.guild.id, whitelist_role_ids=list(whitelist))
        await interaction.response.send_message(f"✅ {role.mention} is now ignored by anti-spam checks.")

    @app_commands.command(name="antiraid-unwhitelist", description="🗑️ Remove a role from anti-spam whitelist")
    async def antiraid_unwhitelist(self, interaction: discord.Interaction, role: discord.Role):
        if not await self.require_mod(interaction):
            return
        config = self.get_config(interaction.guild.id)
        whitelist = set(config.get("whitelist_role_ids", []))
        whitelist.discard(role.id)
        self.update_config(interaction.guild.id, whitelist_role_ids=list(whitelist))
        await interaction.response.send_message(f"🗑️ {role.mention} is no longer whitelisted.")

    # =========================
    # PREFIX COMMANDS
    # =========================

    @commands.command(name="raidlock")
    @commands.has_permissions(manage_guild=True)
    async def raidlock_prefix(self, ctx, *, reason: str = "Manual lockdown"):
        success, msg = await self.lockdown_guild(ctx.guild, reason=reason)
        await ctx.send(msg)

    @commands.command(name="raidunlock")
    @commands.has_permissions(manage_guild=True)
    async def raidunlock_prefix(self, ctx, *, reason: str = "Manual unlock"):
        success, msg = await self.unlock_guild(ctx.guild, reason=reason)
        await ctx.send(msg)

    @commands.command(name="antiraid")
    @commands.has_permissions(manage_guild=True)
    async def antiraid_prefix(self, ctx, mode: str = None):
        if mode is None:
            return await ctx.send("❌ Usage: `!antiraid enable`, `!antiraid disable`, or `!antiraid status`")

        mode = mode.lower()

        if mode == "enable":
            self.update_config(ctx.guild.id, enabled=True)
            return await ctx.send("🛡️ Anti-raid enabled.")

        if mode == "disable":
            self.update_config(ctx.guild.id, enabled=False)
            return await ctx.send("🛡️ Anti-raid disabled.")

        if mode == "status":
            config = self.get_config(ctx.guild.id)
            return await ctx.send(
                f"🛡️ **Anti-Raid Status**\n"
                f"Enabled: `{config.get('enabled')}`\n"
                f"Auto Kick: `{config.get('auto_kick')}`\n"
                f"Lockdown: `{config.get('lockdown')}`"
            )

        await ctx.send("❌ Invalid mode. Use `enable`, `disable`, or `status`.")


async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
