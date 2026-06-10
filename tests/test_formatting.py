"""Unit tests for the formatting helpers."""

import time

from bot.helpers.formatting import (
    human_bytes,
    human_time,
    progress_bar,
    format_progress,
)


def test_human_bytes():
    assert human_bytes(0) == "0 B"
    assert human_bytes(1024) == "1.00 KiB"
    assert human_bytes(1024 * 1024) == "1.00 MiB"
    assert human_bytes(int(1.5 * 1024 ** 3)) == "1.50 GiB"


def test_human_time():
    assert human_time(0) == "00:00"
    assert human_time(65) == "01:05"
    assert human_time(3661) == "01:01:01"
    assert human_time(-1) == "--:--"


def test_progress_bar_bounds():
    assert progress_bar(0).count("█") == 0
    assert progress_bar(100).count("░") == 0
    # Clamps out-of-range values.
    assert progress_bar(150) == progress_bar(100)
    assert progress_bar(-10) == progress_bar(0)


def test_format_progress_contains_fields():
    text = format_progress("Encoding", 50, 100, time.time() - 1)
    assert "Encoding" in text
    assert "Speed" in text
    assert "ETA" in text
