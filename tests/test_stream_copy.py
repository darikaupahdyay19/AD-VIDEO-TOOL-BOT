"""Functional tests asserting multi-input tools copy all source streams."""

import asyncio
import os
import shutil

import pytest

from bot.ffmpeg import operations as ops
from bot.ffmpeg.probe import streams_by_type

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg/ffprobe not available",
)


async def _run(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    assert proc.returncode == 0, err.decode(errors="ignore")


@pytest.fixture()
async def media(tmp_path):
    d = str(tmp_path)
    base = os.path.join(d, "base.mp4")
    srt = os.path.join(d, "exist.srt")
    src = os.path.join(d, "src.mkv")
    new_audio = os.path.join(d, "new.mp3")
    new_sub = os.path.join(d, "new.srt")
    # base clip: 1 video + 1 audio
    await _run(
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", base,
    )
    with open(srt, "w", encoding="utf-8") as fh:
        fh.write("1\n00:00:00,000 --> 00:00:02,000\nExisting\n")
    # src: video + audio + one subtitle stream
    await _run("-i", base, "-i", srt, "-map", "0", "-map", "1", "-c", "copy", src)
    await _run(
        "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
        "-c:a", "libmp3lame", new_audio,
    )
    with open(new_sub, "w", encoding="utf-8") as fh:
        fh.write("1\n00:00:00,000 --> 00:00:02,000\nNew\n")
    return {"src": src, "audio": new_audio, "sub": new_sub}


async def test_add_audio_keeps_all_streams(media):
    out = await ops.add_audio(media["src"], media["audio"], replace=False, language="hin")
    audio = await streams_by_type(out, "audio")
    subs = await streams_by_type(out, "subtitle")
    assert len(await streams_by_type(out, "video")) == 1
    assert len(audio) == 2  # original + appended
    assert len(subs) == 1   # original subtitle preserved
    assert audio[1].language == "hin"


async def test_swap_audio_replaces_but_keeps_other_streams(media):
    out = await ops.swap_audio(media["src"], media["audio"], language="hin")
    assert len(await streams_by_type(out, "audio")) == 1  # replaced
    assert len(await streams_by_type(out, "subtitle")) == 1  # kept
    assert (await streams_by_type(out, "audio"))[0].language == "hin"


async def test_add_subtitle_keeps_all_streams(media):
    out = await ops.add_subtitle(media["src"], media["sub"], language="spa")
    subs = await streams_by_type(out, "subtitle")
    assert len(await streams_by_type(out, "audio")) == 1  # original audio kept
    assert len(subs) == 2  # original + appended
    assert subs[1].language == "spa"


async def test_add_audio_subtitle_keeps_all_and_appends_both(media):
    out = await ops.add_audio_subtitle(
        media["src"], media["audio"], media["sub"],
        audio_language="jpn", subtitle_language="kor",
    )
    audio = await streams_by_type(out, "audio")
    subs = await streams_by_type(out, "subtitle")
    assert len(audio) == 2 and audio[1].language == "jpn"
    assert len(subs) == 2 and subs[1].language == "kor"
