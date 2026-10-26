"""SQLite implementation of ``ILibraryPackRepository``.

Atomic insert-missing goes through ``app.db.bulkSql`` (``executemany_rows``
/ ``iter_batches``); the adapter owns a transaction only when the caller
is not inside one — never a nested BEGIN or a hidden commit of foreign
work (TZ §6, ``SqlCanonicalPersistence`` precedent).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.db.bulkSql import executemany_rows, iter_batches
from app.db.database import Database, _in_transaction
from app.db.mapper import to_row
from app.db.models.libraryPack import LibraryPackRow
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteLibraryPackRepository(
    BaseRepository[LibraryPackRow], ILibraryPackRepository,
):

    def __init__(self, db: Database) -> None:
        super().__init__(db, LibraryPackRow)

    async def insert(self, pack: LibraryPackRow) -> None:
        await super().insert(pack)

    async def insert_missing(self, packs: Sequence[LibraryPackRow]) -> int:
        if not packs:
            return 0
        conn = self._db.main_conn
        if _in_transaction.get():
            return await self._insert_missing(conn, packs)
        async with self._db.transaction_on(conn):
            return await self._insert_missing(conn, packs)

    async def _insert_missing(self, conn, packs: Sequence[LibraryPackRow]) -> int:
        cols, _ = to_row(packs[0])
        placeholders = ", ".join("?" * len(cols))
        # ON CONFLICT(pack_uid) DO NOTHING: a concurrent attach or an existing
        # pack is never replaced. A system_name collision or any other
        # constraint violation raises — not silently skipped — and rolls the
        # attach back (TZ §6).
        sql = (
            f"INSERT INTO {self._table} ({', '.join(cols)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({self._pk_col}) DO NOTHING"
        )
        return await executemany_rows(conn, sql, packs)

    async def existing_uids(self, pack_uids: Sequence[str]) -> set[str]:
        found: set[str] = set()
        for batch in iter_batches(sorted(set(pack_uids))):
            placeholders = ", ".join("?" * len(batch))
            sql = (
                f"SELECT {self._pk_col} FROM {self._table} "
                f"WHERE {self._pk_col} IN ({placeholders})"
            )
            async with self._db.conn.execute(sql, list(batch)) as cur:
                for row in await cur.fetchall():
                    found.add(row[0])
        return found

    async def get_by_uid(self, pack_uid: str) -> LibraryPackRow | None:
        return await self.fetch_one("pack_uid = ?", [pack_uid])

    async def get_by_system_name(self, system_name: str) -> LibraryPackRow | None:
        return await self.fetch_one("system_name = ?", [system_name])

    async def list_all(self) -> list[LibraryPackRow]:
        return await self.fetch_all("1=1", [], order="system_name ASC")

    async def list_engine(self) -> list[LibraryPackRow]:
        return await self.fetch_all("owner_world_uid IS NULL", [], order="system_name ASC")

    async def list_world_owned(self, owner_world_uid: str) -> list[LibraryPackRow]:
        return await self.fetch_all(
            "owner_world_uid = ?", [owner_world_uid], order="system_name ASC",
        )

    async def find_instance(
        self,
        owner_world_uid: str,
        source_pack_uid: str,
    ) -> LibraryPackRow | None:
        return await self.fetch_one(
            "owner_world_uid = ? AND source_pack_uid = ?",
            [owner_world_uid, source_pack_uid],
        )

    async def update_metadata(self, pack: LibraryPackRow) -> None:
        await self._db.conn.execute(
            f"UPDATE {self._table} "
            "SET pack_name = ?, display_name = ?, version = ? "
            "WHERE pack_uid = ?",
            [pack.pack_name, pack.display_name, pack.version, pack.pack_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()

    async def delete(self, pack_uid: str) -> None:
        await super().delete(pack_uid)

    async def upsert(self, pack: LibraryPackRow) -> None:
        raise NotImplementedError(
            "library_packs forbids replace semantics — "
            "use insert / insert_missing / update_metadata (TZ §3, §6)",
        )
