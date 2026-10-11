"""Task-owned SQLite units of work, including implicit repository writes.

Queueing SQL on one aiosqlite connection does not isolate coroutines.
Keep the gate until COMMIT/ROLLBACK, not merely until execute returns.
"""
from __future__ import annotations

import asyncio
import sqlite3
from contextlib import asynccontextmanager

import aiosqlite


class GuardedConnection(aiosqlite.Connection):
    def __init__(self, path: str):
        super().__init__(lambda: sqlite3.connect(path), iter_chunk_size=64)
        self._gate = asyncio.Lock()
        self._owner = None
        self._explicit = False

    async def _acquire(self):
        task = asyncio.current_task()
        if self._owner is task:
            return
        await self._gate.acquire()
        self._owner = task

    def _release(self):
        self._owner = None
        self._gate.release()

    def _has_transaction(self):
        try:
            return self._connection is not None and self.in_transaction
        except sqlite3.ProgrammingError:
            return False  # close() has executed on the worker thread

    async def _execute(self, fn, *args, **kwargs):
        # aiosqlite routes SQL, cursor fetches and commit through this seam.
        await self._acquire()
        try:
            pending = asyncio.create_task(super()._execute(fn, *args, **kwargs))
            try:
                return await asyncio.shield(pending)
            except asyncio.CancelledError:
                # Cancellation cannot interrupt SQLite's worker. Wait until
                # its statement completes before rollback or gate release.
                try:
                    await pending
                except Exception:
                    pass
                raise
        except BaseException:
            if not self._explicit and self._has_transaction():
                await super()._execute(self._conn.rollback)
            raise
        finally:
            if not self._explicit and not self._has_transaction():
                self._release()

    @asynccontextmanager
    async def unit_of_work(self):
        await self._acquire()
        self._explicit = True
        try:
            yield
        finally:
            self._explicit = False
            self._release()
