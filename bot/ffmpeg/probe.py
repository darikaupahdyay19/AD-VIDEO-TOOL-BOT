"""ffprobe based media inspection helpers."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StreamInfo:
    """Lightweight description of a single media stream."""

    index: int
    codec_type: str  # video / audio / subtitle / data / attachment
    codec_name: str
    language: Optional[str] = None
    title: Optional[str] = None

    @property
    def label(self) -> str:
        parts = [f"#{self.index}", self.codec_type, self.codec_name]
        if self.language:
            parts.append(f"[{self.language}]")
        if self.title:
            parts.append(self.title)
        return " ".join(parts)


async def _run_ffprobe(args: List[str]) -> str:
    """Run ffprobe and return its stdout as text."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.decode(errors='ignore')}")
    return stdout.decode(errors="ignore")


async def probe(path: str) -> Dict[str, Any]:
    """Return the full ``ffprobe -show_format -show_streams`` JSON document."""
    out = await _run_ffprobe(
        [
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ]
    )
    return json.loads(out or "{}")


async def get_duration(path: str) -> float:
    """Return the media duration in seconds (``0.0`` when unavailable)."""
    data = await probe(path)
    try:
        return float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        return 0.0


async def get_streams(path: str) -> List[StreamInfo]:
    """Return the list of streams contained in ``path``."""
    data = await probe(path)
    streams: List[StreamInfo] = []
    for raw in data.get("streams", []):
        tags = raw.get("tags", {}) or {}
        streams.append(
            StreamInfo(
                index=raw.get("index", 0),
                codec_type=raw.get("codec_type", "unknown"),
                codec_name=raw.get("codec_name", "unknown"),
                language=tags.get("language"),
                title=tags.get("title"),
            )
        )
    return streams


async def streams_by_type(path: str, codec_type: str) -> List[StreamInfo]:
    """Return only the streams matching ``codec_type``."""
    return [s for s in await get_streams(path) if s.codec_type == codec_type]


@dataclass
class VideoMeta:
    """Video attributes Telegram needs to render a proper preview."""

    duration: int = 0
    width: int = 0
    height: int = 0


async def get_video_meta(path: str) -> VideoMeta:
    """Return ``(duration, width, height)`` for the first video stream.

    Values default to ``0`` when they cannot be determined, which Pyrogram
    tolerates.  Telegram uses them to show the correct length and aspect ratio
    instead of a ``0:00`` placeholder.
    """
    data = await probe(path)
    duration = 0.0
    try:
        duration = float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0
    width = height = 0
    for raw in data.get("streams", []):
        if raw.get("codec_type") == "video":
            try:
                width = int(raw.get("width", 0) or 0)
                height = int(raw.get("height", 0) or 0)
            except (TypeError, ValueError):
                width = height = 0
            # Fall back to the stream duration when the container lacks one.
            if duration <= 0:
                try:
                    duration = float(raw.get("duration", 0.0) or 0.0)
                except (TypeError, ValueError):
                    duration = 0.0
            break
    return VideoMeta(duration=int(round(duration)), width=width, height=height)


__all__ = [
    "StreamInfo",
    "VideoMeta",
    "probe",
    "get_duration",
    "get_streams",
    "streams_by_type",
    "get_video_meta",
]
