"""Throttled progress reporters for Telegram transfers and FFmpeg jobs."""

from __future__ import annotations

import time
from typing import Optional

from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import InlineKeyboardMarkup, Message

from bot.config import Config
from bot.helpers.formatting import format_progress, human_time
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class ProgressReporter:
    """Edits a status :class:`~pyrogram.types.Message` at a throttled cadence.

    A single instance is reused across a task's stages (download → process →
    upload) so the user sees one continuously updated message.
    """

    def __init__(
        self,
        message: Message,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ) -> None:
        self._message = message
        self._reply_markup = reply_markup
        self._last_edit = 0.0
        self._last_text = ""

    async def _safe_edit(self, text: str, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_edit < Config.PROGRESS_UPDATE_INTERVAL:
            return
        if text == self._last_text:
            return
        self._last_edit = now
        self._last_text = text
        try:
            await self._message.edit_text(text, reply_markup=self._reply_markup)
        except MessageNotModified:
            pass
        except FloodWait as exc:
            logger.debug("FloodWait while editing progress: %ss", exc.value)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Progress edit failed: %s", exc)

    async def transfer(self, current: int, total: int, stage: str) -> None:
        """Pyrogram download/upload callback (``current``/``total`` in bytes)."""
        text = format_progress(stage, current, total, self._start_for(stage))
        await self._safe_edit(text)

    _stage_starts: dict

    def _start_for(self, stage: str) -> float:
        if not hasattr(self, "_stage_starts"):
            self._stage_starts = {}
        return self._stage_starts.setdefault(stage, time.time())

    async def ffmpeg(
        self,
        stage: str,
        processed: float,
        total: float,
        speed: float,
        start: float,
    ) -> None:
        """FFmpeg progress callback (seconds-based)."""
        percentage = (processed / total * 100) if total else 0.0
        eta = ((total - processed) / speed) if (speed and total) else 0
        text = (
            f"**{stage}**\n"
            f"`{percentage:.1f}%` • {human_time(processed)} / {human_time(total)}\n"
            f"**Speed:** `{speed:.2f}x`\n"
            f"**ETA:** `{human_time(eta)}`"
        )
        await self._safe_edit(text)

    async def set_text(self, text: str) -> None:
        """Force an immediate status update (e.g. 'Queued', 'Completed')."""
        await self._safe_edit(text, force=True)


__all__ = ["ProgressReporter"]
