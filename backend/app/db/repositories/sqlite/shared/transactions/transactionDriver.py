"""Driver commands and cancellation-safe worker acknowledgement; no row IO."""

import asyncio
from collections.abc import Callable

import aiosqlite

from app.application.publication.errors import PublicationInfrastructureError
from app.db.guardedConnection import GuardedConnection


class SqliteTransactionDriver:
    def _require_owner(self, conn: GuardedConnection) -> None:
        if not conn.owns_unit_of_work:
            raise PublicationInfrastructureError("transaction command requires the owning task's UOW")

    async def begin(self, conn: GuardedConnection, *, write: bool) -> None:
        self._require_owner(conn)
        await conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")

    async def _acknowledge(self, conn: GuardedConnection, function: Callable, *arguments) -> bool:
        self._require_owner(conn)
        # The owner holds the gate. The shield child queues directly on the same
        # worker rather than trying to reacquire the owner's GuardedConnection gate.
        pending = asyncio.create_task(aiosqlite.Connection._execute(conn, function, *arguments))
        cancelled = False
        while not pending.done():
            try:
                await asyncio.shield(pending)
            except asyncio.CancelledError:
                cancelled = True
        pending.result()  # Failure is not proof of rollback; coordinator quarantines.
        return cancelled

    async def commit(self, conn: GuardedConnection) -> bool:
        return await self._acknowledge(conn, conn._conn.execute, "COMMIT")

    async def rollback(self, conn: GuardedConnection) -> bool:
        return await self._acknowledge(conn, conn._conn.execute, "ROLLBACK")

    async def close(self, conn: GuardedConnection) -> None:
        self._require_owner(conn)
        try:
            await self._acknowledge(conn, conn._conn.close)
        finally:
            # Stop the driver only after physical close has drained queued work.
            await conn.close()
