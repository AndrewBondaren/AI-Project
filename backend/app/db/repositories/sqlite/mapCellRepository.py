from app.db.database import Database
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteMapCellRepository(BaseRepository[MapCell], IMapCellRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, MapCell)

    async def get_by_world(self, world_uid: str) -> list[MapCell]:
        return await self.fetch_all("world_uid = ?", [world_uid])

    async def upsert(self, cell: MapCell) -> None:
        await super().upsert(cell)

    async def delete_by_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM map_cells WHERE world_uid = ?", [world_uid]
        )
        await self._db.conn.commit()
