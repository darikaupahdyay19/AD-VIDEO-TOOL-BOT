"""Tests for the async task queue and rate limiter."""

import asyncio

import pytest

from bot.utils.queue import QueuedTask, TaskQueue
from bot.utils.ratelimit import RateLimiter


@pytest.mark.asyncio
async def test_queue_runs_task():
    q = TaskQueue()
    q.start(num_workers=2)
    done = asyncio.Event()

    async def runner(task):
        done.set()

    await q.add(QueuedTask(user_id=1, tool="encode", runner=runner))
    await asyncio.wait_for(done.wait(), timeout=2)
    await q.stop()
    assert done.is_set()


@pytest.mark.asyncio
async def test_queue_cancel_pending():
    q = TaskQueue()
    started = asyncio.Event()

    async def runner(task):
        started.set()
        await asyncio.sleep(5)

    # No workers started yet, so the task stays queued and can be cancelled.
    task = await q.add(QueuedTask(user_id=7, tool="encode", runner=runner))
    cancelled = await q.cancel(task.task_id, user_id=7)
    assert cancelled
    assert not started.is_set()


def test_rate_limiter_blocks_after_max():
    limiter = RateLimiter(max_events=3, window=60)
    assert limiter.is_allowed(1)
    assert limiter.is_allowed(1)
    assert limiter.is_allowed(1)
    assert not limiter.is_allowed(1)
    # A different user is unaffected.
    assert limiter.is_allowed(2)
