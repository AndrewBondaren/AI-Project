from collections.abc import Sequence

from app.db.bulkSql import upsert_rows
from app.db.database import Database, _in_transaction
from app.db.models.locationLevel import LocationLevel
from app.db.repositories.iLocationLevelRepository import ILocationLevelRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteLocationLevelRepository(BaseRepository[LocationLevel], ILocationLevelRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, LocationLevel)

    async def get_by_location(self, location_uid: str) -> list[LocationLevel]:
        return await self.fetch_all("location_uid = ?", [location_uid], order="z ASC")

    async def upsert_bulk(self, rows: Sequence[LocationLevel]) -> int:
        if not rows:
            return 0
        if _in_transaction.get():
            await upsert_rows(self._db.conn, rows)
            return len(rows)
        async with self._db.transaction():
            await upsert_rows(self._db.conn, rows)
        return len(rows)
