"""SQLite relief grade instances/systems — R43 bake-writer."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import asynccontextmanager

from app.db.bulkSql import executemany_rows, iter_batches
from app.db.database import Database, _in_transaction
from app.db.mapper import to_row
from app.db.models.reliefGradeInstance import ReliefGradeInstanceRow
from app.db.models.reliefGradeSystem import ReliefGradeSystemRow
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository
from app.db.repositories.sqlite.base import BaseRepository

# SQLite bind limit for IN (?), not executemany batch (see bulkSql).
UID_IN_BATCH_SIZE = 400


class SqliteReliefGradeRepository(IReliefGradeRepository):
    def __init__(self, db: Database) -> None:
        self._instances = BaseRepository(db, ReliefGradeInstanceRow)
        self._systems = BaseRepository(db, ReliefGradeSystemRow)
        self._db = db

    @asynccontextmanager
    async def persist_session(self):
        async with self._db.transaction():
            yield

    async def upsert_instance(self, row: ReliefGradeInstanceRow) -> None:
        await self._instances.upsert(row)

    async def upsert_system(self, row: ReliefGradeSystemRow) -> None:
        await self._systems.upsert(row)

    async def upsert_instances(self, rows: Sequence[ReliefGradeInstanceRow]) -> None:
        await self._upsert_many(self._instances, rows)

    async def upsert_systems(self, rows: Sequence[ReliefGradeSystemRow]) -> None:
        await self._upsert_many(self._systems, rows)

    async def _upsert_many(self, base: BaseRepository, rows: Sequence[object]) -> None:
        if not rows:
            return
        if _in_transaction.get():
            await self._executemany_replace(base, rows)
            return
        async with self._db.transaction():
            await self._executemany_replace(base, rows)

    async def _executemany_replace(self, base: BaseRepository, rows: Sequence[object]) -> None:
        cols, _ = to_row(rows[0])
        placeholders = ", ".join("?" * len(cols))
        sql = (
            f"INSERT OR REPLACE INTO {base._table} ({', '.join(cols)}) "
            f"VALUES ({placeholders})"
        )
        await executemany_rows(self._db.conn, sql, rows)

    async def list_instances_by_uids(
        self,
        world_uid: str,
        uids: Sequence[str],
    ) -> list[ReliefGradeInstanceRow]:
        unique = list(dict.fromkeys(uids))
        if not unique:
            return []
        out: list[ReliefGradeInstanceRow] = []
        for chunk in iter_batches(unique, size=UID_IN_BATCH_SIZE):
            placeholders = ",".join("?" * len(chunk))
            rows = await self._instances.fetch_all(
                where=f"world_uid = ? AND grade_uid IN ({placeholders})",
                params=[world_uid, *chunk],
            )
            out.extend(rows)
        return out

    async def list_instances_for_world(self, world_uid: str) -> list[ReliefGradeInstanceRow]:
        return await self._instances.fetch_all(
            where="world_uid = ?",
            params=[world_uid],
        )

    async def delete_instances_for_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            f"DELETE FROM {ReliefGradeInstanceRow.__table__} WHERE world_uid = ?",
            [world_uid],
        )
        await self._db.conn.execute(
            f"DELETE FROM {ReliefGradeSystemRow.__table__} WHERE world_uid = ?",
            [world_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()
