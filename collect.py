import time

import discord
from discord.ext import commands
from discord import app_commands

from cogs._statebank_utils import parse_amount, format_money

from database import (
    add_coins,
    set_collect_role,
    remove_collect_role,
    get_collect_roles,
    get_last_collect,
    set_last_collect,
)


def can_manage_server(member: discord.Member):
    return (
        isinstance(member, discord.Member)
        and (
            member.guild_permissions.manage_guild
            or member.guild_permissions.administrator
        )
    )


def format_time(seconds: int):
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class Collect(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def run_collect(self, member: discord.Member):
        if not member.guild:
            return None, "❌ This command must be used in a server."

        rewards = get_collect_roles(member.guild.id)

        if not rewards:
            return None, "❌ No collect rewards are set up in this server yet."

        now = time.time()
        member_role_ids = {role.id for role in member.roles}

        earned_total = 0
        collected_lines = []
        cooldown_lines = []

        for role_id, amount, cooldown in rewards:
            role = member.guild.get_role(role_id)

            if not role:
                continue

            if role_id not in member_role_ids:
                continue

            last = get_last_collect(member.id, member.guild.id, role_id)
            remaining = int(cooldown - (now - last))

            if remaining > 0:
                cooldown_lines.append(f"{role.mention} — ready in **{format_time(remaining)}**")
                continue

            add_coins(member.id, amount)
            set_last_collect(member.id, member.guild.id, role_id)

            earned_total += amount
            collected_lines.append(f"{role.mention} — **{format_money(amount)} Coins**")

        if earned_total <= 0:
            embed = discord.Embed(
                title="🏦 State Bank Collect",
                description="You have no rewards ready to collect.",
                color=discord.Color.orange()
            )

            if cooldown_lines:
                embed.add_field(
                    name="⏳ On Cooldown",
                    value="\n".join(cooldown_lines[:10]),
                    inline=False
                )
            else:
                embed.add_field(
                    name="No Eligible Roles",
                    value="You do not have any roles with collect rewards.",
                    inline=False
                )

            embed.set_footer(text="State Bank • Role Collect Rewards")
            return embed, None

        embed = discord.Embed(
            title="🏦 State Bank Collect",
            description=f"{member.mention} collected **{format_money(earned_total)} Coins**.",
            color=discord.Color.green()
        )

        embed.add_field(
            name="✅ Rewards Collected",
            value="\n".join(collected_lines[:10]),
            inline=False
        )

        if cooldown_lines:
            embed.add_field(
                name="⏳ Still On Cooldown",
                value="\n".join(cooldown_lines[:10]),
                inline=False
            )

        embed.set_footer(text="State Bank • Role Collect Rewards")
        return embed, None

    async def build_collect_list(self, guild: discord.Guild):
        rewards = get_collect_roles(guild.id)

        embed = discord.Embed(
            title="🏦 State Bank Collect Rewards",
            color=discord.Color.gold()
        )

        if not rewards:
            embed.description = "No collect rewards are set up in this server yet."
            return embed

        lines = []

        for role_id, amount, cooldown in rewards:
            role = guild.get_role(role_id)
            role_text = role.mention if role else f"`Missing Role {role_id}`"
            lines.append(
                f"{role_text} — **{format_money(amount)} Coins** every **{format_time(cooldown)}**"
            )

        embed.description = "\n\n".join(lines[:20])
        embed.set_footer(text="Use /collect or !collect to claim ready rewards.")
        return embed

    @app_commands.command(name="collect", description="🏦 Collect role-based State Bank money")
    async def collect_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, error = await self.run_collect(interaction.user)

        if error:
            return await interaction.followup.send(error, ephemeral=True)

        await interaction.followup.send(embed=embed)

    @commands.command(name="collect")
    async def collect_prefix(self, ctx):
        embed, error = await self.run_collect(ctx.author)

        if error:
            return await ctx.send(error)

        await ctx.send(embed=embed)

    @app_commands.command(name="collect-list", description="📜 View State Bank role collect rewards")
    async def collect_list_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if not interaction.guild:
            return await interaction.followup.send("❌ This command must be used in a server.", ephemeral=True)

        embed = await self.build_collect_list(interaction.guild)
        await interaction.followup.send(embed=embed)

    @commands.command(name="collectlist")
    async def collect_list_prefix(self, ctx):
        if not ctx.guild:
            return await ctx.send("❌ This command must be used in a server.")

        embed = await self.build_collect_list(ctx.guild)
        await ctx.send(embed=embed)

    @app_commands.command(name="add-collect-role", description="🏦 Manager only: add a role collect reward")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def add_collect_role_slash(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        amount: str,
        cooldown_minutes: int
    ):
        if not can_manage_server(interaction.user):
            return await interaction.response.send_message(
                "❌ You need **Manage Server** permission.",
                ephemeral=True
            )

        try:
            parsed_amount = parse_amount(amount, minimum=1)
        except ValueError as e:
            return await interaction.response.send_message(f"❌ {e}", ephemeral=True)

        if cooldown_minutes <= 0:
            return await interaction.response.send_message(
                "❌ Cooldown must be above 0 minutes.",
                ephemeral=True
            )

        cooldown_seconds = cooldown_minutes * 60
        set_collect_role(interaction.guild.id, role.id, parsed_amount, cooldown_seconds)

        embed = discord.Embed(
            title="🏦 Collect Role Added",
            description=(
                f"{role.mention} can now collect **{format_money(parsed_amount)} Coins** "
                f"every **{format_time(cooldown_seconds)}**."
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    @commands.command(name="addcollectrole")
    @commands.has_permissions(manage_guild=True)
    async def add_collect_role_prefix(
        self,
        ctx,
        role: discord.Role = None,
        amount: str = None,
        cooldown_minutes: int = None
    ):
        if role is None or amount is None or cooldown_minutes is None:
            return await ctx.send("❌ Usage: `!addcollectrole @role <amount> <cooldown_minutes>`")

        try:
            parsed_amount = parse_amount(amount, minimum=1)
        except ValueError as e:
            return await ctx.send(f"❌ {e}")

        if cooldown_minutes <= 0:
            return await ctx.send("❌ Cooldown must be above 0 minutes.")

        cooldown_seconds = cooldown_minutes * 60
        set_collect_role(ctx.guild.id, role.id, parsed_amount, cooldown_seconds)

        await ctx.send(
            f"🏦 {role.mention} can now collect **{format_money(parsed_amount)} Coins** "
            f"every **{format_time(cooldown_seconds)}**."
        )

    @app_commands.command(name="remove-collect-role", description="🗑️ Manager only: remove a role collect reward")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def remove_collect_role_slash(self, interaction: discord.Interaction, role: discord.Role):
        if not can_manage_server(interaction.user):
            return await interaction.response.send_message(
                "❌ You need **Manage Server** permission.",
                ephemeral=True
            )

        removed = remove_collect_role(interaction.guild.id, role.id)

        if not removed:
            return await interaction.response.send_message(
                "❌ That role does not have a collect reward.",
                ephemeral=True
            )

        await interaction.response.send_message(f"🗑️ Removed collect reward from {role.mention}.")

    @commands.command(name="removecollectrole")
    @commands.has_permissions(manage_guild=True)
    async def remove_collect_role_prefix(self, ctx, role: discord.Role = None):
        if role is None:
            return await ctx.send("❌ Usage: `!removecollectrole @role`")

        removed = remove_collect_role(ctx.guild.id, role.id)

        if not removed:
            return await ctx.send("❌ That role does not have a collect reward.")

        await ctx.send(f"🗑️ Removed collect reward from {role.mention}.")


async def setup(bot):
    await bot.add_cog(Collect(bot))
