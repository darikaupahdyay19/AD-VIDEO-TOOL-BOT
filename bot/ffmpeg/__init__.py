"""FFmpeg subpackage: probing, process management and high level operations."""

from bot.ffmpeg import operations
from bot.ffmpeg.probe import (
    StreamInfo,
    get_duration,
    get_streams,
    probe,
    streams_by_type,
)
from bot.ffmpeg.processor import FFmpegError, FFmpegProcessor

__all__ = [
    "operations",
    "StreamInfo",
    "get_duration",
    "get_streams",
    "probe",
    "streams_by_type",
    "FFmpegError",
    "FFmpegProcessor",
]
