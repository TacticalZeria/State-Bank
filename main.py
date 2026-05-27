import os
import asyncio
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv(override=True)

TOKEN = os.getenv("TOKEN")

EXPECTED_SLASH_COMMANDS = {
    "achievement-list",
    "achievements",
    "admin-panel",
    "balance",
    "blackjack",
    "coinflip",
    "deposit",
    "give-achievement",
    "leaderboard",
    "profile",
    "remove-achievement",
    "rob",
    "roulette",
    "slots",
    "withdraw",
}

print("\n=============================================")
print("🚀 Florida State Bank Bot Starting")
print("=============================================")
print(f"🔑 Token loaded: {bool(TOKEN)}")

if not TOKEN:
    raise RuntimeError("TOKEN missing from .env")

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

bot.remove_command("help")


@bot.event
async def on_ready():
    print("\n=============================================")
    print(f"✅ Logged in as {bot.user}")
    print("🔎 Checking slash commands before sync...")
    print("=============================================")

    local_commands = bot.tree.get_commands()
    local_names = {cmd.name for cmd in local_commands}

    print(f"📌 Local slash command(s): {len(local_commands)}")
    for cmd in sorted(local_commands, key=lambda c: c.name):
        print(f"   • /{cmd.name}")

    missing_local = EXPECTED_SLASH_COMMANDS - local_names
    extra_local = local_names - EXPECTED_SLASH_COMMANDS

    if missing_local:
        print("\n⚠️ Expected but NOT found locally:")
        for name in sorted(missing_local):
            print(f"   ❌ /{name}")
    else:
        print("\n✅ All expected slash commands exist locally.")

    if extra_local:
        print("\nℹ️ Extra local slash commands:")
        for name in sorted(extra_local):
            print(f"   • /{name}")

    print("\n🔄 Syncing slash commands...")

    try:
        synced = await bot.tree.sync()
        synced_names = {cmd.name for cmd in synced}

        print(f"⚡ Synced {len(synced)} slash command(s)")
        for cmd in sorted(synced, key=lambda c: c.name):
            print(f"   ✅ /{cmd.name}")

        missing_synced = EXPECTED_SLASH_COMMANDS - synced_names

        if missing_synced:
            print("\n🚨 Expected but NOT synced:")
            for name in sorted(missing_synced):
                print(f"   ❌ /{name}")
        else:
            print("\n✅ All expected slash commands synced.")

    except Exception as e:
        print("❌ Slash sync failed")
        print(f"{type(e).__name__}: {e}")
        traceback.print_exc()

    print("\n🤖 Bot is online!\n")


async def load_cogs():
    cogs_path = os.path.join(os.getcwd(), "cogs")

    print("\n=============================================")
    print("📂 Loading Cogs")
    print("=============================================")
    print(f"📍 Folder: {cogs_path}\n")

    if not os.path.exists(cogs_path):
        print("❌ No cogs folder found.")
        return

    loaded = []
    failed = []

    for file in sorted(os.listdir(cogs_path)):
        if not file.endswith(".py"):
            continue

        if file.startswith("_"):
            continue

        module = f"cogs.{file[:-3]}"
        path = os.path.join(cogs_path, file)

        print(f"➡️ {file}")

        try:
            await bot.load_extension(module)
            loaded.append(file)
            print("   ✅ Loaded")

        except Exception as e:
            failed.append(file)
            print("   ❌ Failed")
            print(f"   📦 Module: {module}")
            print(f"   📍 Path: {path}")
            print(f"   🧨 {type(e).__name__}: {e}")
            traceback.print_exc()

        print("---------------------------------------------")

    print("\n=============================================")
    print("📊 Cog Summary")
    print("=============================================")
    print(f"✅ Loaded: {len(loaded)}")
    for file in loaded:
        print(f"   • {file}")

    print(f"\n❌ Failed: {len(failed)}")
    for file in failed:
        print(f"   • {file}")

    print("=============================================\n")


async def main():
    try:
        async with bot:
            await load_cogs()
            await bot.start(TOKEN)

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")

    except Exception as e:
        print("\n❌ Startup failed")
        print(f"{type(e).__name__}: {e}")
        traceback.print_exc()


asyncio.run(main())
