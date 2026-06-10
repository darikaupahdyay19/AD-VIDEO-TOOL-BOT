"""High level FFmpeg operations backing the bot's video tools.

Every public coroutine in this module builds an FFmpeg argument list, runs it
through :class:`~bot.ffmpeg.processor.FFmpegProcessor` and returns the path(s) of
the produced file(s).  The functions are intentionally pure with respect to
Telegram – they only deal with files on disk – which keeps them unit-testable
and reusable.
"""

from __future__ import annotations

import asyncio
import os
from typing import List, Optional

from bot.ffmpeg.probe import get_duration, get_video_meta, streams_by_type
from bot.ffmpeg.processor import FFmpegProcessor, ProgressCallback
from bot.utils.logger import get_logger

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Lookup tables
# --------------------------------------------------------------------------- #

VIDEO_CODECS = {
    "h264": "libx264",
    "h265": "libx265",
    "av1": "libaom-av1",
    "vp9": "libvpx-vp9",
}

# Quality preset -> Constant Rate Factor. ``custom`` is handled separately.
QUALITY_CRF = {
    "low": 28,
    "medium": 23,
    "high": 18,
}

AUDIO_CODECS = {
    "mp3": "libmp3lame",
    "aac": "aac",
    "flac": "flac",
    "m4a": "aac",
    "wav": "pcm_s16le",
}

RESOLUTIONS = {
    "240p": 240,
    "360p": 360,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
}

# Selectable stream languages mapped to their ISO 639-2/B codes, used to tag
# muxed audio/subtitle streams via ``-metadata:s:<stream> language=<code>``.
LANGUAGES = {
    "eng": "English",
    "hin": "Hindi",
    "spa": "Spanish",
    "fre": "French",
    "ger": "German",
    "jpn": "Japanese",
    "kor": "Korean",
    "chi": "Chinese",
    "ara": "Arabic",
    "rus": "Russian",
    "por": "Portuguese",
    "tam": "Tamil",
    "tel": "Telugu",
    "und": "Undefined",
}

# Overlay position expressions for image watermarks (main=W/H, overlay=w/h).
OVERLAY_POSITIONS = {
    "top_left": "10:10",
    "top_right": "W-w-10:10",
    "bottom_left": "10:H-h-10",
    "bottom_right": "W-w-10:H-h-10",
    "center": "(W-w)/2:(H-h)/2",
}

# drawtext position expressions for text watermarks (tw/th = text dimensions).
TEXT_POSITIONS = {
    "top_left": "10:10",
    "top_right": "w-tw-10:10",
    "bottom_left": "10:h-th-10",
    "bottom_right": "w-tw-10:h-th-10",
    "center": "(w-tw)/2:(h-th)/2",
}


def _with_suffix(path: str, suffix: str, ext: Optional[str] = None) -> str:
    """Return a sibling path with ``suffix`` appended to the stem."""
    directory = os.path.dirname(path)
    stem, original_ext = os.path.splitext(os.path.basename(path))
    new_ext = f".{ext.lstrip('.')}" if ext else original_ext
    return os.path.join(directory, f"{stem}{suffix}{new_ext}")


# --------------------------------------------------------------------------- #
# Encoding / conversion
# --------------------------------------------------------------------------- #

async def encode(
    input_path: str,
    codec: str = "h264",
    quality: str = "medium",
    crf: Optional[int] = None,
    preset: str = "medium",
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Re-encode ``input_path`` with the requested codec and quality."""
    vcodec = VIDEO_CODECS.get(codec.lower(), "libx264")
    if crf is None:
        crf = QUALITY_CRF.get(quality.lower(), 23)

    output = _with_suffix(input_path, f"_{codec.lower()}")
    args = [
        "-i",
        input_path,
        "-c:v",
        vcodec,
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-c:a",
        "copy",
        output,
    ]
    duration = await get_duration(input_path)
    await FFmpegProcessor(progress, stage="Encoding").run(args, duration)
    return output


async def convert(
    input_path: str,
    target_format: str,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Remux/convert ``input_path`` into ``target_format`` (mp4/mkv/avi/...)."""
    output = _with_suffix(input_path, "_converted", ext=target_format)
    # Stream copy where possible; fall back to re-encoding handled by FFmpeg.
    args = ["-i", input_path, "-c", "copy", output]
    duration = await get_duration(input_path)
    processor = FFmpegProcessor(progress, stage="Converting")
    try:
        await processor.run(args, duration)
    except Exception:
        # Container may not support stream copy – re-encode as a fallback.
        args = ["-i", input_path, output]
        await FFmpegProcessor(progress, stage="Converting").run(args, duration)
    return output


async def multi_resolution(
    input_path: str,
    resolutions: List[str],
    progress: Optional[ProgressCallback] = None,
) -> List[str]:
    """Generate one output per requested resolution and return their paths."""
    outputs: List[str] = []
    duration = await get_duration(input_path)
    for res in resolutions:
        height = RESOLUTIONS.get(res)
        if not height:
            continue
        output = _with_suffix(input_path, f"_{res}")
        args = [
            "-i",
            input_path,
            "-vf",
            f"scale=-2:{height}",
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-preset",
            "medium",
            "-c:a",
            "copy",
            output,
        ]
        await FFmpegProcessor(progress, stage=f"Encoding {res}").run(args, duration)
        outputs.append(output)
    return outputs


# --------------------------------------------------------------------------- #
# Merging / muxing
# --------------------------------------------------------------------------- #

async def merge_videos(
    first: str,
    second: str,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Concatenate two videos using the concat filter (re-encodes).

    The output keeps one video track plus every audio track common to both
    inputs (``min`` of the two audio-stream counts), so multi-language audio is
    preserved. Subtitle streams cannot pass through the concat filter and are
    therefore not carried over by this tool.
    """
    output = _with_suffix(first, "_merged", ext="mkv")
    audio_n = min(
        len(await streams_by_type(first, "audio")),
        len(await streams_by_type(second, "audio")),
    )
    seg0 = "[0:v:0]" + "".join(f"[0:a:{i}]" for i in range(audio_n))
    seg1 = "[1:v:0]" + "".join(f"[1:a:{i}]" for i in range(audio_n))
    out_labels = "[v]" + "".join(f"[a{i}]" for i in range(audio_n))
    filtergraph = f"{seg0}{seg1}concat=n=2:v=1:a={audio_n}{out_labels}"
    args = ["-i", first, "-i", second, "-filter_complex", filtergraph, "-map", "[v]"]
    for i in range(audio_n):
        args += ["-map", f"[a{i}]"]
    args.append(output)
    duration = await get_duration(first) + await get_duration(second)
    await FFmpegProcessor(progress, stage="Merging").run(args, duration)
    return output


def _language_metadata(stream: str, language: Optional[str]) -> List[str]:
    """Build ``-metadata:s:<stream> language=<code>`` args (empty when unset)."""
    if not language:
        return []
    return [f"-metadata:s:{stream}", f"language={language}"]


# Map every keepable stream of the source video (video, audio, subtitle and
# attachments). Data streams (e.g. mp4 ``mebx``) are intentionally excluded as
# they frequently cannot be copied into Matroska and would abort the mux.
_KEEP_ALL_VIDEO = ["-map", "0:v?", "-map", "0:a?", "-map", "0:s?", "-map", "0:t?"]
# Same, but without the source audio (used when replacing the audio track).
_KEEP_ALL_NO_AUDIO = ["-map", "0:v?", "-map", "0:s?", "-map", "0:t?"]


async def add_audio(
    video: str,
    audio: str,
    replace: bool = False,
    language: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Add (or replace) an audio track, copying every other stream verbatim.

    By default (``replace=False``) all of the video's existing streams are
    preserved and the new audio is appended. With ``replace=True`` the source
    audio is dropped while video/subtitle/attachment streams are still copied.
    When ``language`` (an ISO 639-2 code) is given the newly muxed audio stream
    is tagged with it.
    """
    output = _with_suffix(video, "_audio", ext="mkv")
    if replace:
        maps = [*_KEEP_ALL_NO_AUDIO, "-map", "1:a?"]
        new_audio_index = 0
    else:
        maps = [*_KEEP_ALL_VIDEO, "-map", "1:a?"]
        # The appended track sits after any pre-existing audio streams.
        new_audio_index = len(await streams_by_type(video, "audio"))
    args = [
        "-i",
        video,
        "-i",
        audio,
        *maps,
        "-c",
        "copy",
        *_language_metadata(f"a:{new_audio_index}", language),
        output,
    ]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Muxing audio").run(args, duration)
    return output


async def swap_audio(
    video: str,
    audio: str,
    language: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Replace the existing audio track (keeps every non-audio stream)."""
    return await add_audio(
        video, audio, replace=True, language=language, progress=progress
    )


async def add_subtitle(
    video: str,
    subtitle: str,
    language: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Soft-mux a subtitle file, copying every existing stream verbatim.

    All of the video's streams are preserved and the subtitle is appended.
    When ``language`` is given, the newly added subtitle stream is tagged with
    that ISO 639-2 language code.
    """
    output = _with_suffix(video, "_subbed", ext="mkv")
    # The new subtitle is appended after any subtitle streams already present.
    new_sub_index = len(await streams_by_type(video, "subtitle"))
    args = [
        "-i",
        video,
        "-i",
        subtitle,
        *_KEEP_ALL_VIDEO,
        "-map",
        "1:s?",
        "-c",
        "copy",
        *_language_metadata(f"s:{new_sub_index}", language),
        output,
    ]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Muxing subtitle").run(args, duration)
    return output


async def add_audio_subtitle(
    video: str,
    audio: str,
    subtitle: str,
    audio_language: Optional[str] = None,
    subtitle_language: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Mux an external audio track and subtitle, copying every stream verbatim.

    All of the video's existing streams are preserved; the new audio and
    subtitle are appended after their respective same-type streams and can be
    tagged with the given ISO 639-2 language codes.
    """
    output = _with_suffix(video, "_audiosub", ext="mkv")
    new_audio_index = len(await streams_by_type(video, "audio"))
    new_sub_index = len(await streams_by_type(video, "subtitle"))
    args = [
        "-i",
        video,
        "-i",
        audio,
        "-i",
        subtitle,
        *_KEEP_ALL_VIDEO,
        "-map",
        "1:a?",
        "-map",
        "2:s?",
        "-c",
        "copy",
        *_language_metadata(f"a:{new_audio_index}", audio_language),
        *_language_metadata(f"s:{new_sub_index}", subtitle_language),
        output,
    ]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Muxing A+S").run(args, duration)
    return output


async def intro_sub(
    video: str,
    text: str = "Subtitles by Video Tool Bot",
    duration_seconds: int = 5,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Insert an intro subtitle shown for the first ``duration_seconds``.

    A small SRT file is generated on the fly and soft-muxed into the video so
    the intro can be toggled by the player.
    """
    srt_path = _with_suffix(video, "_intro", ext="srt")
    with open(srt_path, "w", encoding="utf-8") as handle:
        handle.write(
            "1\n00:00:00,000 --> "
            f"00:00:{duration_seconds:02d},000\n{text}\n"
        )
    try:
        return await add_subtitle(video, srt_path, progress=progress)
    finally:
        if os.path.exists(srt_path):
            os.remove(srt_path)


async def hardsub(
    video: str,
    subtitle: str,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Burn ``subtitle`` permanently into the video using the subtitles filter."""
    output = _with_suffix(video, "_hardsub", ext="mp4")
    # Escape characters that are special to the lavfi filtergraph parser.
    escaped = subtitle.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    args = [
        "-i",
        video,
        "-vf",
        f"subtitles='{escaped}'",
        "-c:a",
        "copy",
        output,
    ]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Burning subtitles").run(args, duration)
    return output


# --------------------------------------------------------------------------- #
# Stream removal / metadata
# --------------------------------------------------------------------------- #

async def remove_subs(
    video: str,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Drop all subtitle streams while copying everything else."""
    output = _with_suffix(video, "_nosubs")
    args = ["-i", video, "-map", "0", "-map", "-0:s", "-c", "copy", output]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Removing subtitles").run(args, duration)
    return output


async def remove_audio(
    video: str,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Drop all audio streams."""
    output = _with_suffix(video, "_noaudio")
    args = ["-i", video, "-map", "0", "-map", "-0:a", "-c", "copy", output]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Removing audio").run(args, duration)
    return output


async def remove_streams(
    video: str,
    stream_types: List[str],
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Remove the given stream types (``audio``/``subtitle``/``data``/...)."""
    type_to_specifier = {
        "audio": "a",
        "subtitle": "s",
        "data": "d",
        "attachment": "t",
    }
    output = _with_suffix(video, "_stripped")
    args = ["-i", video, "-map", "0"]
    for stream_type in stream_types:
        specifier = type_to_specifier.get(stream_type.lower())
        if specifier:
            args += ["-map", f"-0:{specifier}"]
    args += ["-c", "copy", output]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Removing streams").run(args, duration)
    return output


async def strip_metadata(
    video: str,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Remove all global and per-stream metadata (``-map_metadata -1``)."""
    output = _with_suffix(video, "_nometa")
    args = [
        "-i",
        video,
        "-map",
        "0",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-c",
        "copy",
        output,
    ]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Stripping metadata").run(args, duration)
    return output


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #

async def extract_audio(
    video: str,
    target_format: str = "mp3",
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Extract the first audio track into ``target_format``."""
    codec = AUDIO_CODECS.get(target_format.lower(), "libmp3lame")
    output = _with_suffix(video, "_audio", ext=target_format)
    args = ["-i", video, "-vn", "-map", "0:a:0", "-c:a", codec, output]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Extracting audio").run(args, duration)
    return output


async def extract_subs(
    video: str,
    target_format: str = "srt",
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Extract the first subtitle track into ``target_format`` (srt/ass/vtt)."""
    output = _with_suffix(video, "_subs", ext=target_format)
    args = ["-i", video, "-map", "0:s:0", output]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Extracting subtitles").run(args, duration)
    return output


# --------------------------------------------------------------------------- #
# Watermarking
# --------------------------------------------------------------------------- #

async def watermark_image(
    video: str,
    image: str,
    position: str = "bottom_right",
    opacity: float = 0.7,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Overlay an image watermark at ``position`` with the given ``opacity``."""
    output = _with_suffix(video, "_wm", ext="mp4")
    overlay_xy = OVERLAY_POSITIONS.get(position, OVERLAY_POSITIONS["bottom_right"])
    opacity = max(0.0, min(1.0, opacity))
    filtergraph = (
        f"[1:v]format=rgba,colorchannelmixer=aa={opacity}[wm];"
        f"[0:v][wm]overlay={overlay_xy}"
    )
    args = [
        "-i",
        video,
        "-i",
        image,
        "-filter_complex",
        filtergraph,
        "-c:a",
        "copy",
        output,
    ]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Watermarking").run(args, duration)
    return output


async def watermark_text(
    video: str,
    text: str,
    position: str = "bottom_right",
    opacity: float = 0.7,
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Draw a text watermark at ``position`` with the given ``opacity``."""
    output = _with_suffix(video, "_wmtext", ext="mp4")
    text_xy = TEXT_POSITIONS.get(position, TEXT_POSITIONS["bottom_right"])
    x_expr, _, y_expr = text_xy.partition(":")
    opacity = max(0.0, min(1.0, opacity))
    safe_text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")
    drawtext = (
        f"drawtext=text='{safe_text}':x={x_expr}:y={y_expr}:"
        f"fontsize=24:fontcolor=white@{opacity}:"
        "box=1:boxcolor=black@0.4:boxborderw=8"
    )
    args = ["-i", video, "-vf", drawtext, "-c:a", "copy", output]
    duration = await get_duration(video)
    await FFmpegProcessor(progress, stage="Watermarking").run(args, duration)
    return output


async def generate_thumbnail(video: str) -> Optional[str]:
    """Extract a single JPEG frame to use as a Telegram video thumbnail.

    Returns the thumbnail path, or ``None`` if extraction fails. The frame is
    grabbed a couple of seconds in (falling back to the first frame for very
    short clips) and scaled down to keep it within Telegram's thumb limits.
    """
    thumb = _with_suffix(video, "_thumb", ext="jpg")
    meta = await get_video_meta(video)
    seek = "2" if meta.duration and meta.duration > 3 else "0"
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        seek,
        "-i",
        video,
        "-frames:v",
        "1",
        "-vf",
        "scale='min(320,iw)':-2",
        thumb,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0 and os.path.exists(thumb) and os.path.getsize(thumb):
            return thumb
        logger.warning(
            "Thumbnail generation failed: %s", stderr.decode(errors="ignore")
        )
    except Exception as exc:  # never let a thumbnail failure break the upload
        logger.warning("Thumbnail generation error: %s", exc)
    return None


__all__ = [
    "VIDEO_CODECS",
    "QUALITY_CRF",
    "AUDIO_CODECS",
    "RESOLUTIONS",
    "generate_thumbnail",
    "encode",
    "convert",
    "multi_resolution",
    "merge_videos",
    "add_audio",
    "swap_audio",
    "add_subtitle",
    "add_audio_subtitle",
    "intro_sub",
    "hardsub",
    "remove_subs",
    "remove_audio",
    "remove_streams",
    "strip_metadata",
    "extract_audio",
    "extract_subs",
    "watermark_image",
    "watermark_text",
    "streams_by_type",
]
