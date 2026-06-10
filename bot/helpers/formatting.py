"""Small, dependency-free formatting helpers used across the bot."""

from __future__ import annotations

import math
import time
from typing import Optional


def human_bytes(num: float) -> str:
    """Return a human readable representation of a byte count."""
    if not num:
        return "0 B"
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    power = min(int(math.log(num, 1024)), len(units) - 1)
    value = num / (1024 ** power)
    return f"{value:.2f} {units[power]}"


def human_time(seconds: float) -> str:
    """Format a duration in seconds as ``HH:MM:SS`` (or ``MM:SS``)."""
    if seconds is None or seconds < 0 or math.isinf(seconds) or math.isnan(seconds):
        return "--:--"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def progress_bar(percentage: float, length: int = 12) -> str:
    """Return a text progress bar like ``[█████░░░░░░░]`` for ``percentage``."""
    percentage = max(0.0, min(100.0, percentage))
    filled = int(length * percentage / 100)
    return "[" + "█" * filled + "░" * (length - filled) + "]"


def format_progress(
    stage: str,
    current: float,
    total: float,
    start_time: float,
    speed: Optional[float] = None,
) -> str:
    """Build a multi-line progress message.

    Args:
        stage: human readable stage name (Downloading/Uploading/Encoding...).
        current: bytes/frames processed so far.
        total: total bytes/frames expected (``0`` when unknown).
        start_time: ``time.time()`` captured when the stage started.
        speed: optional explicit speed in bytes/sec; computed when omitted.
    """
    elapsed = max(time.time() - start_time, 1e-6)
    percentage = (current / total * 100) if total else 0.0
    if speed is None:
        speed = current / elapsed
    eta = ((total - current) / speed) if (speed and total) else 0

    return (
        f"**{stage}**\n"
        f"{progress_bar(percentage)} `{percentage:.1f}%`\n"
        f"**Done:** `{human_bytes(current)}` / `{human_bytes(total)}`\n"
        f"**Speed:** `{human_bytes(speed)}/s`\n"
        f"**ETA:** `{human_time(eta)}`"
    )


__all__ = [
    "human_bytes",
    "human_time",
    "progress_bar",
    "format_progress",
]
