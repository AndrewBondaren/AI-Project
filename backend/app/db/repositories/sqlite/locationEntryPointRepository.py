from collections.abc import Sequence

from app.db.bulkSql import executemany_rows
from app.db.database import Database, _in_transaction
from app.db.mapper import to_row
from app.db.models.locationEntryPoint import LocationEntryPoint
from app.db.repositories.iLocationEntryPointRepository import ILocationEntryPointRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteLocationEntryPointRepository(
    BaseRepository[LocationEntryPoint], ILocationEntryPointRepository,
):

    def __init__(self, db: Database) -> None:
        super().__init__(db, LocationEntryPoint)

    async def get_by_location(self, location_uid: str) -> list[LocationEntryPoint]:
        return await self.fetch_all("location_uid = ?", [location_uid], order="entry_role ASC")

    async def upsert_bulk(self, rows: Sequence[LocationEntryPoint]) -> int:
        if not rows:
            return 0
        if _in_transaction.get():
            await self._replace_many(rows)
            return len(rows)
        async with self._db.transaction():
            await self._replace_many(rows)
        return len(rows)

    async def _replace_many(self, rows: Sequence[LocationEntryPoint]) -> None:
        cols, _ = to_row(rows[0])
        placeholders = ", ".join("?" * len(cols))
        sql = (
            f"INSERT OR REPLACE INTO {self._table} ({', '.join(cols)}) "
            f"VALUES ({placeholders})"
        )
        await executemany_rows(self._db.conn, sql, rows)
