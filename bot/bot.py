"""Application lifecycle: start/stop the client and its dependencies.

This module wires together the Pyrogram client, the MongoDB connection and the
async task queue, and exposes :func:`run` as the single blocking entry point
used by both ``main.py`` and ``python -m bot``.
"""

from __future__ import annotations

from pyrogram import idle

from bot import app
from bot.config import Config
from bot.database import db
from bot.helpers.files import ensure_base_dir
from bot.utils.logger import get_logger
from bot.utils.queue import queue

logger = get_logger("bot")


async def _startup() -> None:
    """Validate configuration and bring all subsystems online."""
    Config.validate()
    ensure_base_dir()
    await db.connect()
    queue.start()
    await app.start()
    me = await app.get_me()
    logger.info("✅ %s started as @%s", Config.BOT_NAME, me.username)


async def _shutdown() -> None:
    """Gracefully tear everything down."""
    logger.info("Shutting down…")
    await queue.stop()
    await app.stop()
    await db.close()


async def _main() -> None:
    await _startup()
    await idle()
    await _shutdown()


def run() -> None:
    """Blocking entry point that runs the bot until interrupted."""
    app.run(_main())


__all__ = ["run"]
