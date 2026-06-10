"""Core task orchestration: download → FFmpeg operation → upload → cleanup.

Callback handlers build an :class:`Operation` describing the work to perform and
hand it to :func:`schedule`.  The operation is wrapped in a
:class:`~bot.utils.queue.QueuedTask` and executed by the global worker pool, with
a single :class:`~bot.helpers.progress.ProgressReporter` driving the live status
message through every stage.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Union

from pyrogram import Client
from pyrogram.types import Message

from bot.config import Config
from bot.database import db
from bot.helpers.files import cleanup, file_size, within_size_limit
from bot.helpers.formatting import human_bytes
from bot.helpers.progress import ProgressReporter
from bot.keyboards import cancel_task_keyboard
from bot.utils.logger import get_logger
from bot.utils.queue import QueuedTask, queue

logger = get_logger(__name__)

# An operation receives the shared ProgressReporter and returns the produced
# file path or a list of paths.
OperationResult = Union[str, List[str]]
OperationFn = Callable[["ProgressReporter"], Awaitable[OperationResult]]


async def download_media(
    message: Message,
    work_dir: str,
    reporter: ProgressReporter,
    stage: str = "Downloading",
) -> str:
    """Download the media in ``message`` into ``work_dir`` showing progress.

    Returns the local path of the downloaded file.

    Raises:
        ValueError: when the message carries no downloadable media or the file
            exceeds the configured size limit.
    """
    media = (
        message.video
        or message.document
        or message.audio
        or message.animation
    )
    if media is None:
        raise ValueError("message contains no downloadable media")
    if getattr(media, "file_size", 0) and not within_size_limit(media.file_size):
        raise ValueError(
            f"file is too large ({human_bytes(media.file_size)}); "
            f"limit is {human_bytes(Config.MAX_FILE_SIZE)}"
        )
    await reporter.set_text(f"📥 **{stage}**…")
    path = await message.download(
        file_name=os.path.join(work_dir, ""),
        progress=reporter.transfer,
        progress_args=(stage,),
    )
    if not path:
        raise RuntimeError("download failed")
    return path


@dataclass
class Operation:
    """A unit of FFmpeg work ready to be scheduled."""

    tool: str
    runner: OperationFn
    work_dir: str
    send_as_document: bool = False
    caption: str = ""


async def schedule(
    client: Client,
    user_id: int,
    chat_id: int,
    status_message: Message,
    operation: Operation,
) -> None:
    """Queue ``operation`` for execution, updating the user on its position."""

    async def task_runner(task: QueuedTask) -> None:
        await _execute(client, chat_id, status_message, operation, task)

    queued = QueuedTask(user_id=user_id, tool=operation.tool, runner=task_runner)
    try:
        await queue.add(queued)
    except RuntimeError as exc:
        await status_message.edit_text(f"⚠️ {exc}")
        cleanup(operation.work_dir)
        return

    await db.record_tool_usage(operation.tool)
    position = queue.position(queued.task_id)
    if position > 1:
        await status_message.edit_text(
            f"🕓 **Queued** at position `{position}`.\n"
            f"Tool: `{operation.tool}`",
            reply_markup=cancel_task_keyboard(queued.task_id),
        )


async def _execute(
    client: Client,
    chat_id: int,
    status_message: Message,
    operation: Operation,
    task: QueuedTask,
) -> None:
    """Run a single operation end-to-end (already inside a worker)."""
    reporter = ProgressReporter(
        status_message, reply_markup=cancel_task_keyboard(task.task_id)
    )
    completed = False
    try:
        await reporter.set_text(f"⚙️ **Processing** with `{operation.tool}`…")
        result = await operation.runner(reporter)
        outputs = result if isinstance(result, list) else [result]
        outputs = [path for path in outputs if path and os.path.exists(path)]
        if not outputs:
            raise RuntimeError("operation produced no output")

        for index, path in enumerate(outputs, start=1):
            size = file_size(path)
            if not within_size_limit(size):
                await client.send_message(
                    chat_id,
                    f"⚠️ Output `{os.path.basename(path)}` "
                    f"({human_bytes(size)}) exceeds the upload limit; skipped.",
                )
                continue
            await reporter.set_text(
                f"📤 **Uploading** ({index}/{len(outputs)}) "
                f"`{os.path.basename(path)}`…"
            )
            await _upload(client, chat_id, path, operation, reporter)

        completed = True
        await reporter.set_text("✅ **Completed!**")
        await db.increment_processed(task.user_id, len(outputs))
    except asyncio.CancelledError:
        await reporter.set_text("🛑 **Cancelled.**")
        raise
    except Exception as exc:
        logger.exception("Processing failed for task %s", task.task_id)
        await reporter.set_text(f"❌ **Failed:** `{str(exc)[:300]}`")
    finally:
        await db.record_task_result(completed)
        cleanup(operation.work_dir)


async def _upload(
    client: Client,
    chat_id: int,
    path: str,
    operation: Operation,
    reporter: ProgressReporter,
) -> None:
    """Send a produced file as video, audio, document or generic file."""
    ext = os.path.splitext(path)[1].lower()
    caption = operation.caption or os.path.basename(path)
    progress_args = ("Uploading",)

    if operation.send_as_document:
        await client.send_document(
            chat_id, path, caption=caption,
            progress=reporter.transfer, progress_args=progress_args,
        )
    elif ext in {".mp4", ".mkv", ".mov", ".webm", ".avi"}:
        await client.send_video(
            chat_id, path, caption=caption,
            progress=reporter.transfer, progress_args=progress_args,
        )
    elif ext in {".mp3", ".aac", ".flac", ".wav", ".m4a"}:
        await client.send_audio(
            chat_id, path, caption=caption,
            progress=reporter.transfer, progress_args=progress_args,
        )
    else:
        await client.send_document(
            chat_id, path, caption=caption,
            progress=reporter.transfer, progress_args=progress_args,
        )


__all__ = ["Operation", "schedule"]
