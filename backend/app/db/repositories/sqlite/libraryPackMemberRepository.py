"""SQLite implementation of ``ILibraryPackMemberRepository``.

Same transaction contract as ``SqlCanonicalPersistence`` /
``SqliteLibraryPackRepository``: bulk insert-missing via
``app.db.bulkSql``, owned transaction only outside a caller one.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.db.bulkSql import executemany_rows, iter_batches
from app.db.database import Database, _in_transaction
from app.db.mapper import from_row, to_row
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteLibraryPackMemberRepository(
    BaseRepository[LibraryPackMemberRow], ILibraryPackMemberRepository,
):

    def __init__(self, db: Database) -> None:
        super().__init__(db, LibraryPackMemberRow)

    async def insert(self, member: LibraryPackMemberRow) -> None:
        await super().insert(member)

    async def insert_missing(self, members: Sequence[LibraryPackMemberRow]) -> int:
        if not members:
            return 0
        conn = self._db.main_conn
        if _in_transaction.get():
            return await self._insert_missing(conn, members)
        async with self._db.transaction_on(conn):
            return await self._insert_missing(conn, members)

    async def _insert_missing(self, conn, members: Sequence[LibraryPackMemberRow]) -> int:
        cols, _ = to_row(members[0])
        placeholders = ", ".join("?" * len(cols))
        # ON CONFLICT(template_uid) DO NOTHING: membership never changes the
        # owner of an existing row. A UNIQUE(pack_uid, library_kind, local_uid)
        # collision or FK violation raises and rolls the batch back (TZ §3, §6).
        sql = (
            f"INSERT INTO {self._table} ({', '.join(cols)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({self._pk_col}) DO NOTHING"
        )
        return await executemany_rows(conn, sql, members)

    async def existing_uids(self, template_uids: Sequence[str]) -> set[str]:
        found: set[str] = set()
        for batch in iter_batches(sorted(set(template_uids))):
            placeholders = ", ".join("?" * len(batch))
            sql = (
                f"SELECT {self._pk_col} FROM {self._table} "
                f"WHERE {self._pk_col} IN ({placeholders})"
            )
            async with self._db.conn.execute(sql, list(batch)) as cur:
                for row in await cur.fetchall():
                    found.add(row[0])
        return found

    async def get_by_uid(self, template_uid: str) -> LibraryPackMemberRow | None:
        return await self.fetch_one("template_uid = ?", [template_uid])

    async def find_by_local_uid(
        self,
        pack_uid: str,
        library_kind: str,
        local_uid: str,
    ) -> LibraryPackMemberRow | None:
        return await self.fetch_one(
            "pack_uid = ? AND library_kind = ? AND local_uid = ?",
            [pack_uid, library_kind, local_uid],
        )

    async def list_by_pack(self, pack_uid: str) -> list[LibraryPackMemberRow]:
        return await self.fetch_all("pack_uid = ?", [pack_uid], order="local_uid ASC")

    async def list_by_packs(self, pack_uids: Sequence[str]) -> list[LibraryPackMemberRow]:
        found: list[LibraryPackMemberRow] = []
        for batch in iter_batches(sorted(set(pack_uids))):
            placeholders = ", ".join("?" * len(batch))
            sql = (
                f"SELECT * FROM {self._table} "
                f"WHERE pack_uid IN ({placeholders}) "
                "ORDER BY local_uid ASC"
            )
            async with self._db.conn.execute(sql, list(batch)) as cur:
                rows = await cur.fetchall()
            found.extend(from_row(self._cls, r) for r in rows)
        return found

    async def list_for_world(self, owner_world_uid: str) -> list[LibraryPackMemberRow]:
        sql = (
            f"SELECT m.* FROM {self._table} m "
            "JOIN library_packs p ON p.pack_uid = m.pack_uid "
            "WHERE p.owner_world_uid = ? "
            "ORDER BY m.local_uid ASC"
        )
        async with self._db.conn.execute(sql, [owner_world_uid]) as cur:
            rows = await cur.fetchall()
        return [from_row(self._cls, r) for r in rows]

    async def delete(self, template_uid: str) -> None:
        await super().delete(template_uid)

    async def delete_by_pack(self, pack_uid: str) -> int:
        cur = await self._db.conn.execute(
            f"DELETE FROM {self._table} WHERE pack_uid = ?", [pack_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()
        return cur.rowcount

    async def save(self, member: LibraryPackMemberRow) -> None:
        raise NotImplementedError(
            "library_pack_members has no mutable fields — "
            "identity change is a new row, not a mutation (TZ §2, §3)",
        )

    async def upsert(self, member: LibraryPackMemberRow) -> None:
        raise NotImplementedError(
            "library_pack_members forbids replace semantics — "
            "use insert / insert_missing (TZ §3, §6)",
        )
