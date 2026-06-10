"""Low level FFmpeg process runner with progress reporting and cleanup.

The :class:`FFmpegProcessor` executes a single FFmpeg command, parses the
``-progress pipe:1`` machine readable output and invokes an async callback so
callers can surface real time progress to Telegram.  Processes are tracked so
they can be cancelled and are always cleaned up (terminated/killed) on exit.
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, List, Optional

from bot.config import Config
from bot.utils.logger import get_logger

logger = get_logger(__name__)

# Signature of the progress callback: (stage, processed_seconds, total_seconds,
# speed_multiplier, start_time) -> awaitable
ProgressCallback = Callable[[str, float, float, float, float], Awaitable[None]]


class FFmpegError(RuntimeError):
    """Raised when an FFmpeg invocation exits with a non-zero status."""


class FFmpegProcessor:
    """Runs FFmpeg commands and reports progress.

    Args:
        progress_callback: optional coroutine invoked periodically with the
            current encoding progress.
        stage: label passed to the progress callback (e.g. ``"Encoding"``).
    """

    def __init__(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        stage: str = "Processing",
    ) -> None:
        self._progress_callback = progress_callback
        self._stage = stage
        self._process: Optional[asyncio.subprocess.Process] = None
        self._cancelled = False

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def cancel(self) -> None:
        """Terminate the running FFmpeg process if any."""
        self._cancelled = True
        await self._terminate()

    async def _terminate(self) -> None:
        proc = self._process
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        except ProcessLookupError:  # already gone
            pass

    async def run(self, args: List[str], total_duration: float = 0.0) -> None:
        """Execute ``ffmpeg <args>`` enforcing the configured task timeout.

        Args:
            args: FFmpeg arguments *excluding* the ``ffmpeg`` binary itself.
            total_duration: total media duration in seconds, used to compute the
                progress percentage.

        Raises:
            FFmpegError: when FFmpeg exits non-zero.
            asyncio.CancelledError: when cancelled via :meth:`cancel`.
            asyncio.TimeoutError: when the configured timeout elapses.
        """
        command = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-progress",
            "pipe:1",
            "-nostats",
            *args,
        ]
        logger.info("Running FFmpeg: %s", " ".join(command))

        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            await asyncio.wait_for(
                self._consume(total_duration), timeout=Config.TASK_TIMEOUT
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            await self._terminate()
            raise
        finally:
            # Drain stderr so we can report it and the pipe does not block.
            stderr_data = b""
            if self._process and self._process.stderr is not None:
                stderr_data = await self._process.stderr.read()

        returncode = self._process.returncode
        if self._cancelled:
            raise asyncio.CancelledError("FFmpeg task cancelled")
        if returncode != 0:
            message = stderr_data.decode(errors="ignore").strip().splitlines()
            tail = "\n".join(message[-8:]) if message else "unknown error"
            raise FFmpegError(f"FFmpeg exited with code {returncode}:\n{tail}")

    async def _consume(self, total_duration: float) -> None:
        """Read the ``-progress`` stream and emit progress callbacks."""
        assert self._process is not None and self._process.stdout is not None
        start = time.time()
        last_emit = 0.0
        processed = 0.0
        speed = 0.0

        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            text = line.decode(errors="ignore").strip()
            if "=" not in text:
                continue
            key, _, value = text.partition("=")
            if key == "out_time_ms":
                try:
                    processed = int(value) / 1_000_000
                except ValueError:
                    processed = 0.0
            elif key == "speed":
                try:
                    speed = float(value.replace("x", "").strip())
                except ValueError:
                    speed = 0.0
            elif key == "progress":
                now = time.time()
                should_emit = (
                    value == "end"
                    or now - last_emit >= Config.PROGRESS_UPDATE_INTERVAL
                )
                if should_emit and self._progress_callback is not None:
                    last_emit = now
                    try:
                        await self._progress_callback(
                            self._stage, processed, total_duration, speed, start
                        )
                    except Exception as exc:  # never let UI errors kill the job
                        logger.warning("Progress callback failed: %s", exc)
                if value == "end":
                    break

        await self._process.wait()


__all__ = ["FFmpegProcessor", "FFmpegError", "ProgressCallback"]
