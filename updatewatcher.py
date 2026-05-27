import json
import hashlib
from pathlib import Path

import discord
from discord.ext import commands, tasks

# Channel where the update panel and update posts go.
UPDATE_CHANNEL_ID = 1508415501460701245

# Your user ID can always use the panel.
OWNER_ID = 1125240487507402882

COGS_DIR = Path("cogs")
DATA_DIR = Path("data")
STATE_FILE = DATA_DIR / "cog_update_state.json"

SCAN_SECONDS = 30

IGNORED_FILES = {
    "__init__.py",
    "lock_management_cmds.py",
}


def can_manage_updates(member):
    return getattr(member, "id", None) == OWNER_ID


def hash_file(path: Path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def scan_cogs():
    files = {}

    if not COGS_DIR.exists():
        return files

    for path in sorted(COGS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue

        if path.name in IGNORED_FILES:
            continue

        file_hash = hash_file(path)

        if file_hash:
            files[path.name] = file_hash

    return files


def load_state():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not STATE_FILE.exists():
        return None

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=4), encoding="utf-8")


class UpdatePostModal(discord.ui.Modal):
    def __init__(self, cog, update_type: str, color: discord.Color):
        super().__init__(title=f"Post {update_type}")
        self.cog = cog
        self.update_type = update_type
        self.color = color

        self.update_title = discord.ui.TextInput(
            label="Update Title",
            placeholder="Example: Economy Balance Update",
            required=True,
            max_length=100
        )

        self.summary = discord.ui.TextInput(
            label="Short Summary",
            placeholder="Example: Updated cooldowns and improved command messages.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=900
        )

        self.changes = discord.ui.TextInput(
            label="Changes / Notes",
            placeholder="- Added...\n- Fixed...\n- Changed...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1500
        )

        self.add_item(self.update_title)
        self.add_item(self.summary)
        self.add_item(self.changes)

    async def on_submit(self, interaction: discord.Interaction):
        if not can_manage_updates(interaction.user):
            return await interaction.response.send_message(
                "❌ This panel is owner-only.",
                ephemeral=True
            )

        channel = await self.cog.get_update_channel()

        if channel is None:
            return await interaction.response.send_message(
                f"❌ I could not find the update channel: `{UPDATE_CHANNEL_ID}`",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"🧾 State Bank {self.update_type}",
            description=f"**{self.update_title.value}**\n\n{self.summary.value}",
            color=self.color,
            timestamp=discord.utils.utcnow()
        )

        if self.changes.value.strip():
            embed.add_field(
                name="Changes",
                value=self.changes.value[:1024],
                inline=False
            )

        embed.set_footer(text=f"Posted by {interaction.user.display_name}")

        await channel.send(embed=embed)

        await interaction.response.send_message(
            "✅ Update posted.",
            ephemeral=True
        )


class UpdatePanelView(discord.ui.View):
    def __init__(self, cog=None):
        super().__init__(timeout=None)
        self.cog = cog

    async def check_user(self, interaction: discord.Interaction):
        if not can_manage_updates(interaction.user):
            await interaction.response.send_message(
                "❌ This panel is owner-only.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Post Update",
        style=discord.ButtonStyle.blurple,
        emoji="🧾",
        custom_id="statebank_update_panel:post_update"
    )
    async def post_update(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction):
            return
        await interaction.response.send_modal(
            UpdatePostModal(self.cog, "Update", discord.Color.gold())
        )

    @discord.ui.button(
        label="New Feature",
        style=discord.ButtonStyle.green,
        emoji="✨",
        custom_id="statebank_update_panel:new_feature"
    )
    async def new_feature(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction):
            return
        await interaction.response.send_modal(
            UpdatePostModal(self.cog, "Feature Update", discord.Color.green())
        )

    @discord.ui.button(
        label="Bug Fix",
        style=discord.ButtonStyle.gray,
        emoji="🐛",
        custom_id="statebank_update_panel:bug_fix"
    )
    async def bug_fix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction):
            return
        await interaction.response.send_modal(
            UpdatePostModal(self.cog, "Bug Fix", discord.Color.blurple())
        )

    @discord.ui.button(
        label="Maintenance",
        style=discord.ButtonStyle.red,
        emoji="🛠️",
        custom_id="statebank_update_panel:maintenance"
    )
    async def maintenance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction):
            return
        await interaction.response.send_modal(
            UpdatePostModal(self.cog, "Maintenance Notice", discord.Color.orange())
        )

    @discord.ui.button(
        label="Watcher Status",
        style=discord.ButtonStyle.gray,
        emoji="📡",
        custom_id="statebank_update_panel:watcher_status"
    )
    async def watcher_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction):
            return

        current = scan_cogs()
        saved = load_state() or {}

        embed = discord.Embed(
            title="📡 State Bank Update Watcher",
            description="Automatic cog watcher status.",
            color=discord.Color.blurple()
        )

        embed.add_field(name="Update Channel", value=f"<#{UPDATE_CHANNEL_ID}>", inline=False)
        embed.add_field(name="Watched Cogs", value=str(len(current)), inline=True)
        embed.add_field(name="Saved Baseline", value=str(len(saved)), inline=True)
        embed.add_field(name="Scan Rate", value=f"Every {SCAN_SECONDS}s", inline=True)
        embed.set_footer(text="State Bank • Update Panel")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class UpdateWatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Register persistent panel buttons after restart.
        self.bot.add_view(UpdatePanelView(self))

        self.watcher.start()

    def cog_unload(self):
        self.watcher.cancel()

    async def get_update_channel(self):
        channel = self.bot.get_channel(UPDATE_CHANNEL_ID)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(UPDATE_CHANNEL_ID)
            except Exception:
                return None

        return channel

    def build_panel_embed(self):
        embed = discord.Embed(
            title="🧾 State Bank Update Panel",
            description=(
                "Use the buttons below to post clean update logs without typing commands.\n\n"
                "**Post Update** — General bot update\n"
                "**New Feature** — New command or system\n"
                "**Bug Fix** — Fixed issue or command bug\n"
                "**Maintenance** — Downtime or maintenance notice\n"
                "**Watcher Status** — Check cog watcher status"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(text="State Bank • Staff Update Panel")
        return embed

    async def send_update_notice(self, added=None, changed=None, removed=None):
        added = added or []
        changed = changed or []
        removed = removed or []

        channel = await self.get_update_channel()

        if channel is None:
            print(f"⚠️ UpdateWatcher: Could not find channel {UPDATE_CHANNEL_ID}")
            return

        embed = discord.Embed(
            title="🧾 State Bank Cog Update Detected",
            description="One or more bot cog files were updated.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )

        if changed:
            embed.add_field(
                name="Updated Cogs",
                value="\n".join(f"• `{name}`" for name in changed[:20]),
                inline=False
            )

        if added:
            embed.add_field(
                name="New Cogs",
                value="\n".join(f"• `{name}`" for name in added[:20]),
                inline=False
            )

        if removed:
            embed.add_field(
                name="Removed Cogs",
                value="\n".join(f"• `{name}`" for name in removed[:20]),
                inline=False
            )

        embed.add_field(
            name="Note",
            value="If this update changed commands or loaded code, restart the bot to fully apply it.",
            inline=False
        )

        embed.set_footer(text="State Bank • Automatic Cog Watcher")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"⚠️ UpdateWatcher: Failed to send update notice: {type(e).__name__}: {e}")

    @tasks.loop(seconds=SCAN_SECONDS)
    async def watcher(self):
        current = scan_cogs()
        saved = load_state()

        # First run: save baseline without spamming the channel.
        if saved is None:
            save_state(current)
            return

        added = sorted(set(current) - set(saved))
        removed = sorted(set(saved) - set(current))
        changed = sorted(
            name for name in set(current) & set(saved)
            if current[name] != saved[name]
        )

        if added or removed or changed:
            save_state(current)
            await self.send_update_notice(
                added=added,
                changed=changed,
                removed=removed
            )

    @watcher.before_loop
    async def before_watcher(self):
        await self.bot.wait_until_ready()

    @commands.command(name="updatepanel")
    async def updatepanel_prefix(self, ctx):
        if not can_manage_updates(ctx.author):
            return await ctx.send("❌ This command is owner-only.")
        channel = await self.get_update_channel()

        if channel is None:
            return await ctx.send(f"❌ I could not find the update channel: `{UPDATE_CHANNEL_ID}`")

        await channel.send(
            embed=self.build_panel_embed(),
            view=UpdatePanelView(self)
        )

        await ctx.send(f"✅ Update panel sent to <#{UPDATE_CHANNEL_ID}>.")

    @commands.command(name="updatepost")
    async def updatepost_prefix(self, ctx, *, message: str = None):
        if not can_manage_updates(ctx.author):
            return await ctx.send("❌ This command is owner-only.")

        if not message:
            return await ctx.send("❌ Usage: `!updatepost <update message>`")

        channel = await self.get_update_channel()

        if channel is None:
            return await ctx.send(f"❌ I could not find the update channel: `{UPDATE_CHANNEL_ID}`")

        embed = discord.Embed(
            title="🧾 State Bank Update",
            description=message,
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Posted by {ctx.author.display_name}")

        await channel.send(embed=embed)
        await ctx.send("✅ Update posted.")

    @commands.command(name="updatestatus")
    async def updatestatus_prefix(self, ctx):
        if not can_manage_updates(ctx.author):
            return await ctx.send("❌ This command is owner-only.")

        current = scan_cogs()
        saved = load_state() or {}

        embed = discord.Embed(
            title="🧾 State Bank Update Watcher",
            description="Cog watcher status.",
            color=discord.Color.blurple()
        )

        embed.add_field(name="Update Channel", value=f"<#{UPDATE_CHANNEL_ID}>", inline=False)
        embed.add_field(name="Watched Cogs", value=str(len(current)), inline=True)
        embed.add_field(name="Saved Baseline", value=str(len(saved)), inline=True)
        embed.add_field(name="Scan Rate", value=f"Every {SCAN_SECONDS}s", inline=True)
        embed.set_footer(text="State Bank • Update Watcher")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(UpdateWatcher(bot))
