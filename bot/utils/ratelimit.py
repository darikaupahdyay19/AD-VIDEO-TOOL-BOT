"""In-memory sliding-window rate limiter for flood protection."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from bot.config import Config


class RateLimiter:
    """Simple per-user sliding window limiter.

    Allows at most ``max_events`` actions within ``window`` seconds per user.
    """

    def __init__(self, max_events: int | None = None, window: int | None = None) -> None:
        self._max = max_events or Config.RATE_LIMIT_MAX
        self._window = window or Config.RATE_LIMIT_WINDOW
        self._events: Dict[int, Deque[float]] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> bool:
        """Record an event and return ``False`` when the user is over the limit."""
        now = time.time()
        bucket = self._events[user_id]
        # Drop timestamps outside the window.
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True

    def retry_after(self, user_id: int) -> int:
        """Seconds until the user is allowed again (0 if currently allowed)."""
        bucket = self._events.get(user_id)
        if not bucket or len(bucket) < self._max:
            return 0
        return max(0, int(self._window - (time.time() - bucket[0])))


rate_limiter = RateLimiter()

__all__ = ["RateLimiter", "rate_limiter"]
