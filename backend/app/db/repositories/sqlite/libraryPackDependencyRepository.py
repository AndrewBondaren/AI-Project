"""SQLite implementation of ``ILibraryPackDependencyRepository``.

``required_pack_uid`` carries no FK (TZ §3): a dependency on a
not-yet-imported pack is valid data — incompleteness is diagnosed by the
caller, not enforced here.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.db.bulkSql import executemany_rows, iter_batches
from app.db.database import Database, _in_transaction
from app.db.mapper import from_row, to_row
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.db.repositories.iLibraryPackDependencyRepository import ILibraryPackDependencyRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteLibraryPackDependencyRepository(
    BaseRepository[LibraryPackDependencyRow], ILibraryPackDependencyRepository,
):

    def __init__(self, db: Database) -> None:
        super().__init__(db, LibraryPackDependencyRow)

    async def insert(self, dependency: LibraryPackDependencyRow) -> None:
        await super().insert(dependency)

    async def insert_missing(self, dependencies: Sequence[LibraryPackDependencyRow]) -> int:
        if not dependencies:
            return 0
        conn = self._db.main_conn
        if _in_transaction.get():
            return await self._insert_missing(conn, dependencies)
        async with self._db.transaction_on(conn):
            return await self._insert_missing(conn, dependencies)

    async def _insert_missing(self, conn, dependencies: Sequence[LibraryPackDependencyRow]) -> int:
        cols, _ = to_row(dependencies[0])
        placeholders = ", ".join("?" * len(cols))
        sql = (
            f"INSERT INTO {self._table} ({', '.join(cols)}) "
            f"VALUES ({placeholders}) "
            "ON CONFLICT (pack_uid, required_pack_uid) DO NOTHING"
        )
        return await executemany_rows(conn, sql, dependencies)

    async def list_for_pack(self, pack_uid: str) -> list[LibraryPackDependencyRow]:
        return await self.fetch_all(
            "pack_uid = ?", [pack_uid], order="required_pack_uid ASC",
        )

    async def list_for_packs(self, pack_uids: Sequence[str]) -> list[LibraryPackDependencyRow]:
        found: list[LibraryPackDependencyRow] = []
        for batch in iter_batches(sorted(set(pack_uids))):
            placeholders = ", ".join("?" * len(batch))
            sql = (
                f"SELECT * FROM {self._table} "
                f"WHERE pack_uid IN ({placeholders}) "
                "ORDER BY pack_uid ASC, required_pack_uid ASC"
            )
            async with self._db.conn.execute(sql, list(batch)) as cur:
                rows = await cur.fetchall()
            found.extend(from_row(self._cls, r) for r in rows)
        return found

    async def required_uids(self, pack_uid: str) -> set[str]:
        async with self._db.conn.execute(
            f"SELECT required_pack_uid FROM {self._table} WHERE pack_uid = ?",
            [pack_uid],
        ) as cur:
            return {row[0] for row in await cur.fetchall()}

    async def delete(self, pack_uid: str, required_pack_uid: str) -> None:
        await self._db.conn.execute(
            f"DELETE FROM {self._table} WHERE pack_uid = ? AND required_pack_uid = ?",
            [pack_uid, required_pack_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()

    async def delete_for_pack(self, pack_uid: str) -> int:
        cur = await self._db.conn.execute(
            f"DELETE FROM {self._table} WHERE pack_uid = ?", [pack_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()
        return cur.rowcount

    async def upsert(self, dependency: LibraryPackDependencyRow) -> None:
        raise NotImplementedError(
            "library_pack_dependencies forbids replace semantics — "
            "use insert / insert_missing (TZ §3, §6)",
        )
