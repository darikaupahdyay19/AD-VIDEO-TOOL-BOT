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


__all__ = [
    "StreamInfo",
    "probe",
    "get_duration",
    "get_streams",
    "streams_by_type",
]
