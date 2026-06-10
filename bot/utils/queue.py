"""Asynchronous task queue with per-user and global concurrency control.

Tasks are coroutine callables wrapped in :class:`QueuedTask`.  A pool of worker
coroutines (sized by :data:`Config.MAX_CONCURRENT_TASKS`) pulls work off a global
:class:`asyncio.Queue`.  Per-user limits are enforced via a counter and tasks can
be cancelled individually by id.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional

from bot.config import Config
from bot.utils.logger import get_logger

logger = get_logger(__name__)

# A task body is any zero-argument coroutine function.
TaskCallable = Callable[["QueuedTask"], Awaitable[None]]


@dataclass
class QueuedTask:
    """A unit of work tracked by :class:`TaskQueue`."""

    user_id: int
    tool: str
    runner: TaskCallable
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    status: str = "queued"
    _async_task: Optional[asyncio.Task] = field(default=None, repr=False)
    _cancel_hook: Optional[Callable[[], Awaitable[None]]] = field(
        default=None, repr=False
    )

    def set_cancel_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        """Register a coroutine invoked when the task is cancelled.

        Used by FFmpeg jobs to terminate the underlying subprocess promptly.
        """
        self._cancel_hook = hook


class TaskQueue:
    """A global FIFO queue dispatching work to a fixed pool of workers."""

    def __init__(self) -> None:
        self._queue: "asyncio.Queue[QueuedTask]" = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._tasks: Dict[str, QueuedTask] = {}
        self._per_user: Dict[int, int] = {}
        self._started = False

    # ------------------------------------------------------------------ life
    def start(self, num_workers: Optional[int] = None) -> None:
        """Spawn the worker coroutines (idempotent)."""
        if self._started:
            return
        count = num_workers or Config.MAX_CONCURRENT_TASKS
        for index in range(max(1, count)):
            self._workers.append(asyncio.create_task(self._worker(index)))
        self._started = True
        logger.info("Task queue started with %d worker(s)", len(self._workers))

    async def stop(self) -> None:
        """Cancel all workers and running tasks."""
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
        self._started = False

    # ------------------------------------------------------------- scheduling
    def user_task_count(self, user_id: int) -> int:
        return self._per_user.get(user_id, 0)

    async def add(self, task: QueuedTask) -> QueuedTask:
        """Enqueue ``task``.

        Raises:
            RuntimeError: when the user already has the maximum number of tasks.
        """
        if self.user_task_count(task.user_id) >= Config.MAX_TASKS_PER_USER:
            raise RuntimeError(
                f"You already have {Config.MAX_TASKS_PER_USER} tasks queued."
            )
        self._tasks[task.task_id] = task
        self._per_user[task.user_id] = self.user_task_count(task.user_id) + 1
        await self._queue.put(task)
        logger.debug("Queued task %s (%s) for user %s", task.task_id, task.tool, task.user_id)
        return task

    def position(self, task_id: str) -> int:
        """Approximate queue position (1-based) of ``task_id`` (0 if running)."""
        pending = [t.task_id for t in list(self._queue._queue)]  # type: ignore[attr-defined]
        return pending.index(task_id) + 1 if task_id in pending else 0

    def status(self) -> Dict[str, int]:
        """Return a snapshot of queue metrics."""
        running = sum(1 for t in self._tasks.values() if t.status == "running")
        return {
            "pending": self._queue.qsize(),
            "running": running,
            "total_tracked": len(self._tasks),
        }

    def get(self, task_id: str) -> Optional[QueuedTask]:
        return self._tasks.get(task_id)

    async def cancel(self, task_id: str, user_id: Optional[int] = None) -> bool:
        """Cancel a queued or running task.

        Args:
            task_id: id returned by :meth:`add`.
            user_id: when provided, the task is only cancelled if it belongs to
                this user (prevents cancelling someone else's job).

        Returns:
            ``True`` if a task was cancelled.
        """
        task = self._tasks.get(task_id)
        if not task or (user_id is not None and task.user_id != user_id):
            return False
        task.status = "cancelled"
        if task._cancel_hook is not None:
            try:
                await task._cancel_hook()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Cancel hook failed for %s: %s", task_id, exc)
        if task._async_task is not None:
            task._async_task.cancel()
        return True

    # --------------------------------------------------------------- internal
    def _release(self, task: QueuedTask) -> None:
        remaining = self.user_task_count(task.user_id) - 1
        if remaining > 0:
            self._per_user[task.user_id] = remaining
        else:
            self._per_user.pop(task.user_id, None)
        self._tasks.pop(task.task_id, None)

    async def _worker(self, index: int) -> None:
        logger.debug("Worker %d ready", index)
        while True:
            task = await self._queue.get()
            if task.status == "cancelled":
                self._release(task)
                self._queue.task_done()
                continue
            task.status = "running"
            try:
                task._async_task = asyncio.create_task(task.runner(task))
                await task._async_task
                if task.status != "cancelled":
                    task.status = "completed"
            except asyncio.CancelledError:
                task.status = "cancelled"
                logger.info("Task %s cancelled", task.task_id)
            except Exception as exc:
                task.status = "failed"
                logger.exception("Task %s failed: %s", task.task_id, exc)
            finally:
                self._release(task)
                self._queue.task_done()


# Shared queue instance.
queue = TaskQueue()

__all__ = ["TaskQueue", "QueuedTask", "queue"]
