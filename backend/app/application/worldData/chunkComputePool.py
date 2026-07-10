"""Shared sync compute pool for terrain chunks and climate batches."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from app.application.worldData.pack.packBakeLog import log_pack_compute_pool

T = TypeVar("T")
R = TypeVar("R")


def split_contiguous_batches(items: Sequence[T], workers: int) -> list[list[T]]:
    """Split *items* into at most *workers* contiguous slices (order preserved)."""
    n = len(items)
    if n == 0:
        return []
    batch_count = min(max(1, workers), n)
    size = (n + batch_count - 1) // batch_count
    return [list(items[i : i + size]) for i in range(0, n, size)]


class ChunkComputePool:
    """
    Thread-pool for CPU-bound sync work from async orchestrators.

    ProcessPool can replace executor backend without changing orchestrator API.
    """

    def __init__(
        self,
        workers: int,
        *,
        max_in_flight: int | None = None,
        thread_name_prefix: str = "chunk-compute",
        log_diagnostics: bool = False,
    ) -> None:
        self._workers = max(1, workers)
        self._max_in_flight = max_in_flight or (2 * self._workers)
        self._executor: ThreadPoolExecutor | None = None
        self._thread_name_prefix = thread_name_prefix
        if self._workers > 1:
            self._executor = ThreadPoolExecutor(
                max_workers=self._workers,
                thread_name_prefix=self._thread_name_prefix,
            )
            if log_diagnostics:
                log_pack_compute_pool(workers=self._workers, max_in_flight=self._max_in_flight)

    @property
    def workers(self) -> int:
        return self._workers

    def shutdown(self, *, wait: bool = True) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None

    async def map_sync(
        self,
        items: Sequence[T],
        compute: Callable[[T], R],
    ) -> list[R]:
        """Run *compute* on each item; return results in input order."""
        if not items:
            return []
        if self._workers == 1 or len(items) == 1:
            return [compute(item) for item in items]

        loop = asyncio.get_running_loop()
        sem = asyncio.Semaphore(self._max_in_flight)
        executor = self._executor

        async def run_one(item: T) -> R:
            async with sem:
                return await loop.run_in_executor(executor, compute, item)

        return list(await asyncio.gather(*[run_one(item) for item in items]))

    async def map_sync_with_callback(
        self,
        items: Sequence[T],
        compute: Callable[[T], R],
        on_result: Callable[[T, R], Awaitable[None]],
    ) -> list[R]:
        """Like map_sync but invokes *on_result* under a lock (serial side effects)."""
        if not items:
            return []
        if self._workers == 1 or len(items) == 1:
            results: list[R] = []
            for item in items:
                result = compute(item)
                await on_result(item, result)
                results.append(result)
            return results

        loop = asyncio.get_running_loop()
        sem = asyncio.Semaphore(self._max_in_flight)
        callback_lock = asyncio.Lock()
        ordered: list[R | None] = [None] * len(items)
        executor = self._executor

        async def run_indexed(idx: int, item: T) -> None:
            async with sem:
                result = await loop.run_in_executor(executor, compute, item)
            async with callback_lock:
                await on_result(item, result)
                ordered[idx] = result

        await asyncio.gather(*[run_indexed(i, item) for i, item in enumerate(items)])
        return [r for r in ordered if r is not None]
