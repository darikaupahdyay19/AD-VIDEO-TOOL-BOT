"""Functional tests for video metadata + thumbnail generation (need FFmpeg)."""

import asyncio
import os
import shutil

import pytest

from bot.ffmpeg.operations import generate_thumbnail
from bot.ffmpeg.probe import get_video_meta

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg/ffprobe not available",
)


async def _make_clip(path: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
        "-pix_fmt", "yuv420p", path,
    )
    await proc.communicate()


@pytest.fixture()
async def clip(tmp_path):
    path = os.path.join(str(tmp_path), "clip.mp4")
    await _make_clip(path)
    return path


async def test_get_video_meta_reports_dimensions_and_duration(clip):
    meta = await get_video_meta(clip)
    assert meta.width == 320
    assert meta.height == 240
    assert meta.duration >= 1  # ~2s clip, rounded


async def test_generate_thumbnail_creates_jpeg(clip):
    thumb = await generate_thumbnail(clip)
    try:
        assert thumb is not None
        assert os.path.exists(thumb)
        assert os.path.getsize(thumb) > 0
    finally:
        if thumb and os.path.exists(thumb):
            os.remove(thumb)
