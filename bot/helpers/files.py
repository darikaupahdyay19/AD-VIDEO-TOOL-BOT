"""Filesystem helpers: per-task working directories and cleanup."""

from __future__ import annotations

import os
import shutil
import uuid
from typing import Optional

from bot.config import Config
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def ensure_base_dir() -> str:
    """Ensure the configured download directory exists and return it."""
    os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
    return Config.DOWNLOAD_DIR


def make_work_dir(user_id: int) -> str:
    """Create and return a unique working directory for a single task."""
    base = ensure_base_dir()
    work_dir = os.path.join(base, f"{user_id}_{uuid.uuid4().hex[:8]}")
    os.makedirs(work_dir, exist_ok=True)
    return work_dir


def cleanup(path: Optional[str]) -> None:
    """Best-effort removal of a file or directory tree."""
    if not path:
        return
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.isfile(path):
            os.remove(path)
    except OSError as exc:  # pragma: no cover - defensive
        logger.warning("Failed to clean up %s: %s", path, exc)


def file_size(path: str) -> int:
    """Return the size of ``path`` in bytes (0 when missing)."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def within_size_limit(size: int) -> bool:
    """Return ``True`` when ``size`` is within the configured maximum."""
    return 0 < size <= Config.MAX_FILE_SIZE


__all__ = [
    "ensure_base_dir",
    "make_work_dir",
    "cleanup",
    "file_size",
    "within_size_limit",
]
