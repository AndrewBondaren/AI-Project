"""Generic insert-missing persistence adapter over ``app.db`` shared infra.

Not a repository: the domain supplies the SQL model and the row builder;
bulk insert-missing goes through ``app.db.bulkSql`` (``executemany_rows`` /
``iter_batches``, batch size only ``EXECUTEMANY_BATCH_SIZE`` — bulk-sql rule).

``context`` for this adapter is the ``app.db.database.Database`` (or a
compatible handle exposing ``main_conn`` + ``transaction_on``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.application.canonicalLibrary.adapters import (
    CanonicalAttachResult,
    CanonicalEntry,
    CanonicalSnapshot,
)
from app.db.bulkSql import executemany_rows, iter_batches
from app.db.database import _in_transaction
from app.db.mapper import pk_col, to_row


def _identity_row(entry: CanonicalEntry) -> Any:
    return entry.body


@dataclass(frozen=True)
class SqlCanonicalPersistence:
    """Insert-missing ``CanonicalPersistenceAdapter`` for dataclass SQL models.

    - ``model`` — dataclass model with ``__table__`` / ``__pk__`` (mapper
      ``to_row`` builds the INSERT).
    - ``uid_column`` — column carrying the canonical UID; defaults to the
      model pk column.
    - ``row_of`` — ``CanonicalEntry`` → model instance to insert (default:
      the entry body itself).
    """

    model: type
    uid_column: str | None = None
    row_of: Callable[[CanonicalEntry], Any] = _identity_row

    def __post_init__(self) -> None:
        object.__setattr__(self, "_uid_col", self.uid_column or pk_col(self.model))

    async def insert_missing(
        self,
        snapshot: CanonicalSnapshot,
        context: Any,
    ) -> CanonicalAttachResult:
        declared = [entry.uid for entry in snapshot.entries]
        if not declared:
            return CanonicalAttachResult()
        conn = context.main_conn
        if _in_transaction.get():
            # Caller transaction: participate — no nested BEGIN, no commit
            # of foreign work.
            return await self._attach(conn, snapshot, declared)
        async with context.transaction_on(conn):
            return await self._attach(conn, snapshot, declared)

    async def _attach(
        self,
        conn: Any,
        snapshot: CanonicalSnapshot,
        declared: list[str],
    ) -> CanonicalAttachResult:
        # Check + insert in one transaction: the missing-set cannot go stale
        # between the read and the write.
        existing = await self._existing_uids(conn, declared)
        missing = [entry for entry in snapshot.entries if entry.uid not in existing]
        if missing:
            await self._insert_rows(conn, missing)
        return CanonicalAttachResult(
            added=tuple(entry.uid for entry in missing),
            existing=tuple(uid for uid in declared if uid in existing),
        )

    async def _existing_uids(self, conn: Any, declared: list[str]) -> set[str]:
        found: set[str] = set()
        for batch in iter_batches(declared):
            placeholders = ", ".join("?" * len(batch))
            sql = (
                f"SELECT {self._uid_col} FROM {self.model.__table__} "
                f"WHERE {self._uid_col} IN ({placeholders})"
            )
            async with conn.execute(sql, list(batch)) as cur:
                for row in await cur.fetchall():
                    found.add(row[0])
        return found

    async def _insert_rows(self, conn: Any, missing: list[CanonicalEntry]) -> None:
        rows = [self.row_of(entry) for entry in missing]
        cols, _ = to_row(rows[0])
        placeholders = ", ".join("?" * len(cols))
        # ON CONFLICT(uid) DO NOTHING: a concurrent attach or a user override
        # of a canonical UID is never replaced (TZ §6). Other constraint
        # violations raise — not silently skipped — and roll the attach back.
        sql = (
            f"INSERT INTO {self.model.__table__} ({', '.join(cols)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({self._uid_col}) DO NOTHING"
        )
        await executemany_rows(conn, sql, rows)
