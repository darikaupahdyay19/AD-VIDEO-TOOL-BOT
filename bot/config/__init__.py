"""Centralised configuration loaded from environment variables.

All runtime configuration is read from the process environment (optionally
populated from a ``.env`` file via :mod:`python-dotenv`).  Importing this module
never raises even when variables are missing, so the rest of the package can be
imported safely for tests and tooling.  Use :meth:`Config.validate` at start-up
to fail fast when required values are absent.
"""

from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv

# Load variables from a local .env file if present. ``override=False`` keeps any
# values that are already exported in the real environment.
load_dotenv(override=False)


def _get_int(key: str, default: int = 0) -> int:
    """Return an environment variable parsed as ``int`` (or ``default``)."""
    value = os.getenv(key, "").strip()
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    """Return an environment variable parsed as a boolean."""
    value = os.getenv(key, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "y", "on"}


def _get_int_list(key: str) -> List[int]:
    """Parse a space/comma separated list of integers (e.g. admin ids)."""
    raw = os.getenv(key, "")
    parts = raw.replace(",", " ").split()
    ids: List[int] = []
    for part in parts:
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


class Config:
    """Strongly typed view over the bot's environment configuration."""

    # ----- Telegram / Pyrogram -------------------------------------------------
    API_ID: int = _get_int("API_ID")
    API_HASH: str = os.getenv("API_HASH", "")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    SESSION_NAME: str = os.getenv("SESSION_NAME", "video_tool_bot")
    WORKERS: int = _get_int("WORKERS", 8)

    # ----- Database ------------------------------------------------------------
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "video_tool_bot")

    # ----- Admin / access control ---------------------------------------------
    OWNER_ID: int = _get_int("OWNER_ID")
    ADMIN_IDS: List[int] = _get_int_list("ADMIN_IDS")
    AUTH_CHANNEL: str = os.getenv("AUTH_CHANNEL", "")  # optional force-sub channel
    LOG_CHANNEL: int = _get_int("LOG_CHANNEL")

    # ----- Storage / limits ----------------------------------------------------
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")
    # Maximum input file size in bytes (default 2 GiB which is the Telegram cap
    # for bots that are not connected to a local Bot API server).
    MAX_FILE_SIZE: int = _get_int("MAX_FILE_SIZE", 2 * 1024 * 1024 * 1024)
    # Hard timeout for any single FFmpeg job in seconds (default 2 hours).
    TASK_TIMEOUT: int = _get_int("TASK_TIMEOUT", 2 * 60 * 60)
    # Maximum concurrent FFmpeg jobs handled by the global worker pool.
    MAX_CONCURRENT_TASKS: int = _get_int("MAX_CONCURRENT_TASKS", 2)
    # Maximum queued tasks allowed per user.
    MAX_TASKS_PER_USER: int = _get_int("MAX_TASKS_PER_USER", 5)

    # ----- Rate limiting / flood protection ------------------------------------
    RATE_LIMIT_WINDOW: int = _get_int("RATE_LIMIT_WINDOW", 60)
    RATE_LIMIT_MAX: int = _get_int("RATE_LIMIT_MAX", 20)

    # ----- Misc ----------------------------------------------------------------
    PROGRESS_UPDATE_INTERVAL: int = _get_int("PROGRESS_UPDATE_INTERVAL", 5)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    BOT_NAME: str = os.getenv("BOT_NAME", "Video Tool Bot")
    SUPPORT_CHAT: str = os.getenv("SUPPORT_CHAT", "")

    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Return ``True`` when ``user_id`` is the owner or an admin."""
        return user_id == cls.OWNER_ID or user_id in cls.ADMIN_IDS

    @classmethod
    def validate(cls) -> None:
        """Validate that the mandatory configuration is present.

        Raises:
            RuntimeError: if any required value is missing.
        """
        missing = []
        if not cls.API_ID:
            missing.append("API_ID")
        if not cls.API_HASH:
            missing.append("API_HASH")
        if not cls.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )


__all__ = ["Config"]
