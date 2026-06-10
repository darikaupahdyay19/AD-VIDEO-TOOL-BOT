"""Admin panel commands.

All handlers are gated behind ``filters.user(admin_ids)`` so only the owner and
configured admins can invoke them.  Admin ids are read from the ``OWNER_ID`` and
``ADMIN_IDS`` environment variables via :class:`~bot.config.Config`.
"""

from __future__ import annotations

import asyncio
import os
import sys

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.config import Config
from bot.database import db
from bot.utils.logger import get_logger
from bot.utils.queue import queue

logger = get_logger(__name__)

# Build the admin user filter once. ``filters.user`` accepts a list of ids.
_ADMIN_IDS = list({Config.OWNER_ID, *Config.ADMIN_IDS} - {0})
admin_only = filters.user(_ADMIN_IDS) if _ADMIN_IDS else filters.user([])

LOG_FILE = "bot.log"


@Client.on_message(filters.command("broadcast") & admin_only)
async def broadcast_command(client: Client, message: Message) -> None:
    """Forward/copy the replied-to message to every known user."""
    if not message.reply_to_message:
        await message.reply_text(
            "↩️ Reply to a message with /broadcast to send it to all users."
        )
        return

    user_ids = await db.all_user_ids()
    status = await message.reply_text(f"📣 Broadcasting to {len(user_ids)} users…")
    sent = failed = 0
    for user_id in user_ids:
        try:
            await message.reply_to_message.copy(user_id)
            sent += 1
        except Exception:
            failed += 1
        # Gentle pacing to respect Telegram flood limits.
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"📣 **Broadcast complete.**\n✅ Sent: `{sent}`\n❌ Failed: `{failed}`"
    )


@Client.on_message(filters.command("users") & admin_only)
async def users_command(client: Client, message: Message) -> None:
    total = await db.total_users()
    await message.reply_text(f"👥 Total users: `{total}`")


@Client.on_message(filters.command("stats") & admin_only & filters.create(
    lambda _, __, m: len(m.command) > 1 and m.command[1] == "admin"
))
async def admin_stats_command(client: Client, message: Message) -> None:
    """Extended stats including live queue metrics (``/stats admin``)."""
    stats = await db.get_stats()
    q = queue.status()
    await message.reply_text(
        "🛠 **Admin statistics**\n"
        f"👥 Users: `{stats.total_users}`\n"
        f"🎬 Total tasks: `{stats.total_tasks}`\n"
        f"✅ Completed: `{stats.completed_tasks}`\n"
        f"❌ Failed: `{stats.failed_tasks}`\n"
        f"📦 Queue pending: `{q['pending']}`\n"
        f"⚙️ Queue running: `{q['running']}`"
    )


@Client.on_message(filters.command("ban") & admin_only)
async def ban_command(client: Client, message: Message) -> None:
    target = _extract_target(message)
    if target is None:
        await message.reply_text("Usage: `/ban <user_id>`")
        return
    await db.set_banned(target, True)
    await message.reply_text(f"🚫 User `{target}` banned.")


@Client.on_message(filters.command("unban") & admin_only)
async def unban_command(client: Client, message: Message) -> None:
    target = _extract_target(message)
    if target is None:
        await message.reply_text("Usage: `/unban <user_id>`")
        return
    await db.set_banned(target, False)
    await message.reply_text(f"✅ User `{target}` unbanned.")


@Client.on_message(filters.command("logs") & admin_only)
async def logs_command(client: Client, message: Message) -> None:
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        await message.reply_document(LOG_FILE, caption="📄 Latest logs")
    else:
        await message.reply_text("No log file found yet.")


@Client.on_message(filters.command("restart") & admin_only)
async def restart_command(client: Client, message: Message) -> None:
    await message.reply_text("♻️ Restarting…")
    logger.warning("Restart requested by %s", message.from_user.id)
    await queue.stop()
    # Re-exec the current process. Process managers (Docker/systemd) will also
    # restart the container if this exits.
    os.execv(sys.executable, [sys.executable, "-m", "bot"])


def _extract_target(message: Message) -> int | None:
    """Resolve the target user id from a reply or command argument."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    if len(message.command) > 1:
        try:
            return int(message.command[1])
        except ValueError:
            return None
    return None
