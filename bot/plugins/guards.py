"""Shared access-control helpers for plugins (ban + flood protection)."""

from __future__ import annotations

from pyrogram.types import CallbackQuery, Message

from bot.database import db
from bot.utils.ratelimit import rate_limiter


async def passes_guards(event) -> bool:
    """Return ``True`` when the user may proceed.

    Performs ban checking and sliding-window rate limiting, replying to the user
    with an explanation when blocked.  Works for both :class:`Message` and
    :class:`CallbackQuery` events.
    """
    user = event.from_user
    if user is None:
        return False

    if await db.is_banned(user.id):
        await _reply(event, "🚫 You are banned from using this bot.")
        return False

    if not rate_limiter.is_allowed(user.id):
        retry = rate_limiter.retry_after(user.id)
        await _reply(event, f"⏳ Slow down! Try again in {retry}s.")
        return False

    return True


async def _reply(event, text: str) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
    elif isinstance(event, Message):
        await event.reply_text(text)


__all__ = ["passes_guards"]
