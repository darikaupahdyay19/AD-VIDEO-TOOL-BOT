"""Logging configuration for the bot.

Provides a single :func:`get_logger` helper that returns module level loggers
sharing a consistent format.  The root configuration is applied lazily the first
time a logger is requested so importing the module has no side effects.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from bot.config import Config

_CONFIGURED = False

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_root() -> None:
    """Configure the root logger exactly once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, Config.LOG_LEVEL, logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers when reloaded (e.g. during tests).
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(stream_handler)

    # Persist logs to a file so the /logs admin command can serve them.
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        try:
            file_handler = logging.FileHandler("bot.log")
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            pass

    # Pyrogram is very chatty at INFO level; keep it at WARNING.
    logging.getLogger("pyrogram").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured :class:`logging.Logger` instance."""
    _configure_root()
    return logging.getLogger(name if name else "bot")


__all__ = ["get_logger"]
