"""Tests for FFmpeg operation helpers that do not require FFmpeg itself."""

from bot.ffmpeg import operations as ops
from bot.ffmpeg.operations import _with_suffix


def test_with_suffix_keeps_extension():
    assert _with_suffix("/tmp/clip.mp4", "_x") == "/tmp/clip_x.mp4"


def test_with_suffix_changes_extension():
    assert _with_suffix("/tmp/clip.mp4", "_x", ext="mkv") == "/tmp/clip_x.mkv"
    assert _with_suffix("/tmp/clip.mp4", "_x", ext=".mkv") == "/tmp/clip_x.mkv"


def test_codec_and_quality_tables():
    assert ops.VIDEO_CODECS["h264"] == "libx264"
    assert ops.VIDEO_CODECS["h265"] == "libx265"
    assert ops.VIDEO_CODECS["av1"] == "libaom-av1"
    assert ops.VIDEO_CODECS["vp9"] == "libvpx-vp9"
    assert ops.QUALITY_CRF["low"] > ops.QUALITY_CRF["high"]


def test_resolutions_table():
    assert ops.RESOLUTIONS["720p"] == 720
    assert set(ops.RESOLUTIONS) == {"240p", "360p", "480p", "720p", "1080p"}
