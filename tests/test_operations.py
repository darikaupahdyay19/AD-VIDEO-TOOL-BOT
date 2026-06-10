"""Tests for FFmpeg operation helpers that do not require FFmpeg itself."""

from bot.ffmpeg import operations as ops
from bot.ffmpeg.operations import _language_metadata, _with_suffix


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


def test_languages_table():
    assert ops.LANGUAGES["eng"] == "English"
    assert ops.LANGUAGES["und"] == "Undefined"
    # Codes should be the 3-letter ISO 639-2 form FFmpeg expects.
    assert all(len(code) == 3 for code in ops.LANGUAGES)


def test_language_metadata_builds_args():
    assert _language_metadata("a:0", "eng") == ["-metadata:s:a:0", "language=eng"]
    assert _language_metadata("s:1", "hin") == ["-metadata:s:s:1", "language=hin"]


def test_language_metadata_empty_when_unset():
    assert _language_metadata("a:0", None) == []
    assert _language_metadata("a:0", "") == []
