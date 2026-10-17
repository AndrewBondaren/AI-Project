"""SQLite region_states CRUD; sole state writer is StateChangeConsumer (10a).

No bake/generator state writes or transition logic. Read/bake cleanup may only
delete explicitly tombstoned rows; it never decides which regions are orphaned.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.db.bulkSql import executemany_rows
from app.db.database import Database
from app.db.mapper import to_row
from app.db.models.regionState import RegionStateRow
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.db.repositories.sqlite.base import BaseRepository


@dataclass
class _TombstoneParams:
    updated_at: str
    world_uid: str
    region_uid: str


_MARK_TOMBSTONE = (
    "UPDATE region_states SET tombstone = 1, updated_at = ? "
    "WHERE world_uid = ? AND region_uid = ?"
)


class SqliteRegionStateRepository(IRegionStateRepository):
    def __init__(self, db: Database) -> None:
        self._db = db
        # Composition keeps BaseRepository's single-column save/delete private.
        self._rows = BaseRepository(db, RegionStateRow)

    async def get(self, world_uid: str, region_uid: str) -> RegionStateRow | None:
        return await self._rows.fetch_one(
            "world_uid = ? AND region_uid = ?", [world_uid, region_uid],
        )

    async def get_by_world(self, world_uid: str) -> list[RegionStateRow]:
        return await self._rows.fetch_all(
            "world_uid = ?", [world_uid], order="region_uid ASC",
        )

    async def upsert(self, state: RegionStateRow) -> None:
        async with self._db.transaction_if_needed():
            await self._rows.upsert(state)

    async def upsert_bulk(self, states: Sequence[RegionStateRow]) -> int:
        if not states:
            return 0
        columns, _ = to_row(states[0])
        sql = (
            f"INSERT OR REPLACE INTO region_states ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )
        async with self._db.transaction_if_needed() as conn:
            return await executemany_rows(conn, sql, states)

    async def mark_tombstone(
        self, world_uid: str, region_uid: str, *, updated_at: str,
    ) -> int:
        async with self._db.transaction_if_needed() as conn:
            async with conn.execute(
                _MARK_TOMBSTONE, [updated_at, world_uid, region_uid],
            ) as cursor:
                return cursor.rowcount

    async def mark_tombstones(
        self, world_uid: str, region_uids: Sequence[str], *, updated_at: str,
    ) -> int:
        if not region_uids:
            return 0
        rows = [_TombstoneParams(updated_at, world_uid, uid)
                for uid in dict.fromkeys(region_uids)]
        async with self._db.transaction_if_needed() as conn:
            return await executemany_rows(conn, _MARK_TOMBSTONE, rows)

    async def cleanup_orphans(self, world_uid: str) -> int:
        async with self._db.transaction_if_needed() as conn:
            async with conn.execute(
                "DELETE FROM region_states WHERE world_uid = ? AND tombstone = 1",
                [world_uid],
            ) as cursor:
                return cursor.rowcount
