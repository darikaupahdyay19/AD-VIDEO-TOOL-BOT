"""User-facing slash commands: /start /help /about /settings /ping /stats."""

from __future__ import annotations

import time

from pyrogram import Client, filters
from pyrogram.types import Message

from bot import __version__
from bot.config import Config
from bot.database import db
from bot.keyboards import settings_keyboard
from bot.plugins.guards import passes_guards
from bot.utils.logger import get_logger

logger = get_logger(__name__)

START_TEXT = (
    "👋 **Welcome to {name}!**\n\n"
    "Send me any **video** and I'll show you a menu of tools: encode, convert, "
    "multi-resolution, watermarking, subtitle/audio muxing, stream removal and "
    "much more — all powered by FFmpeg.\n\n"
    "Use /help to see everything I can do."
)

HELP_TEXT = (
    "🛠 **How to use {name}**\n\n"
    "1. Send a video (as a video or document).\n"
    "2. Pick a tool from the inline menu.\n"
    "3. Provide any extra input the tool asks for (audio, subtitle, image…).\n"
    "4. Watch the live progress and receive your processed file!\n\n"
    "**Available tools:** Encode (H264/H265/AV1/VP9), Convert "
    "(MP4/MKV/AVI/MOV/WEBM), Multi-Resolution, Video+Video, Video+Audio, "
    "Video+Subtitle, Video+Audio+Subtitle, IntroSub, HardSub, Remove Subs, "
    "Remove Audio, Remove Streams, Strip Metadata, Extract Subs, Extract Audio, "
    "Swap Audio and Watermark.\n\n"
    "**Commands:** /start /help /about /settings /ping /stats"
)

ABOUT_TEXT = (
    "🤖 **{name}**\n"
    "Version: `{version}`\n"
    "Engine: `Pyrogram + FFmpeg`\n"
    "Database: `MongoDB`\n\n"
    "A production-ready Telegram video processing bot."
)


@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message) -> None:
    if not await passes_guards(message):
        return
    user = message.from_user
    await db.add_user(user.id, user.username, user.first_name)
    await message.reply_text(START_TEXT.format(name=Config.BOT_NAME))


@Client.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message) -> None:
    if not await passes_guards(message):
        return
    await message.reply_text(HELP_TEXT.format(name=Config.BOT_NAME))


@Client.on_message(filters.command("about") & filters.private)
async def about_command(client: Client, message: Message) -> None:
    if not await passes_guards(message):
        return
    await message.reply_text(
        ABOUT_TEXT.format(name=Config.BOT_NAME, version=__version__)
    )


@Client.on_message(filters.command("ping") & filters.private)
async def ping_command(client: Client, message: Message) -> None:
    if not await passes_guards(message):
        return
    start = time.time()
    reply = await message.reply_text("🏓 Pinging…")
    latency = (time.time() - start) * 1000
    await reply.edit_text(f"🏓 **Pong!** `{latency:.0f} ms`")


@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client: Client, message: Message) -> None:
    if not await passes_guards(message):
        return
    settings = await db.get_settings(message.from_user.id)
    await message.reply_text(
        "⚙️ **Your settings**\nTap an option to change it.",
        reply_markup=settings_keyboard(settings),
    )


@Client.on_message(filters.command("stats") & filters.private)
async def stats_command(client: Client, message: Message) -> None:
    if not await passes_guards(message):
        return
    stats = await db.get_stats()
    user = await db.get_user(message.from_user.id)
    processed = user.processed_files if user else 0
    top_tools = sorted(
        stats.tools_usage.items(), key=lambda kv: kv[1], reverse=True
    )[:5]
    tools_lines = "\n".join(f"• `{name}`: {count}" for name, count in top_tools)
    await message.reply_text(
        "📊 **Statistics**\n"
        f"👥 Users: `{stats.total_users}`\n"
        f"🎬 Tasks processed: `{stats.total_tasks}`\n"
        f"✅ Completed: `{stats.completed_tasks}`\n"
        f"❌ Failed: `{stats.failed_tasks}`\n"
        f"🗂 Your files: `{processed}`\n"
        + (f"\n**Top tools:**\n{tools_lines}" if tools_lines else "")
    )
