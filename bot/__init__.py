"""Video Tool Bot package.

Exposes the shared Pyrogram :data:`app` client.  Handlers live in
``bot.plugins`` and are auto-discovered by Pyrogram's smart-plugin loader at
start-up, so importing this package has no network side effects.
"""

from __future__ import annotations

from pyrogram import Client

from bot.config import Config
from bot.utils.logger import get_logger

__version__ = "1.0.0"

logger = get_logger("bot")

# The shared client. Plugins under ``bot/plugins`` are loaded automatically.
app = Client(
    name=Config.SESSION_NAME,
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    workers=Config.WORKERS,
    plugins={"root": "bot.plugins"},
)

__all__ = ["app", "logger", "__version__"]
