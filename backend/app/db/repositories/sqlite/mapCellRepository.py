from app.db.database import Database
from app.db.mapper import to_row
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteMapCellRepository(BaseRepository[MapCell], IMapCellRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, MapCell)

    async def get_by_world(self, world_uid: str) -> list[MapCell]:
        return await self.fetch_all("world_uid = ?", [world_uid])

    async def get_location_uids_with_cells(self, world_uid: str) -> set[str]:
        sql = ("SELECT DISTINCT location_uid FROM map_cells "
               "WHERE world_uid = ? AND location_uid IS NOT NULL")
        async with self._db.conn.execute(sql, [world_uid]) as cur:
            rows = await cur.fetchall()
        return {row[0] for row in rows}

    async def upsert(self, cell: MapCell) -> None:
        await super().upsert(cell)

    async def insert_bulk_ignore(self, cells: list[MapCell]) -> int:
        """INSERT OR IGNORE in a single transaction. Returns actual inserted count."""
        if not cells:
            return 0
        cols, _ = to_row(cells[0])
        placeholders = ", ".join("?" * len(cols))
        sql = f"INSERT OR IGNORE INTO map_cells ({', '.join(cols)}) VALUES ({placeholders})"
        inserted = 0
        for cell in cells:
            _, vals = to_row(cell)
            cur = await self._db.conn.execute(sql, vals)
            inserted += cur.rowcount
        await self._db.conn.commit()
        return inserted

    async def delete_by_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM map_cells WHERE world_uid = ?", [world_uid]
        )
        await self._db.conn.commit()
