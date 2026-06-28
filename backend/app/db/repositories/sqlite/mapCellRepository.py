from app.db.database import Database, _in_transaction
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
        if not _in_transaction.get():
            await self._db.conn.commit()
        return inserted

    async def _upsert_partial(
        self,
        cells: list[MapCell],
        update_clause: str,
        where_clause: str,
    ) -> int:
        if not cells:
            return 0
        cols, _ = to_row(cells[0])
        placeholders = ", ".join("?" * len(cols))
        sql = (
            f"INSERT INTO map_cells ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(world_uid, x, y, z) DO UPDATE SET {update_clause} "
            f"WHERE {where_clause}"
        )
        count = 0
        for cell in cells:
            _, vals = to_row(cell)
            cur = await self._db.conn.execute(sql, vals)
            count += cur.rowcount
        if not _in_transaction.get():
            await self._db.conn.commit()
        return count

    async def upsert_terrain_skeleton(self, cells: list[MapCell]) -> int:
        return await self._upsert_partial(
            cells,
            "system_terrain = excluded.system_terrain",
            "map_cells.system_building_element IS NULL",
        )

    async def upsert_climate_fields(self, cells: list[MapCell]) -> int:
        return await self._upsert_partial(
            cells,
            "temperature_base = excluded.temperature_base, "
            "rainfall = excluded.rainfall, "
            "location_uid = excluded.location_uid, "
            "system_terrain = excluded.system_terrain",
            "map_cells.system_building_element IS NULL",
        )

    async def upsert_ore_markers(self, cells: list[MapCell]) -> int:
        return await self._upsert_partial(
            cells,
            "system_material = excluded.system_material",
            "map_cells.system_building_element IS NULL",
        )

    async def upsert_cave_carve(self, cells: list[MapCell]) -> int:
        return await self._upsert_partial(
            cells,
            "system_terrain = excluded.system_terrain",
            "map_cells.system_building_element IS NULL "
            "AND map_cells.system_material IS NULL",
        )

    async def get_z_slice(
        self,
        world_uid: str,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> list[MapCell]:
        sql = (
            "SELECT * FROM map_cells WHERE world_uid = ? "
            "AND x BETWEEN ? AND ? AND y BETWEEN ? AND ? "
            "AND z BETWEEN ? AND ?"
        )
        params = [world_uid, x_min, x_max, y_min, y_max, z_min, z_max]
        async with self._db.conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        from app.db.mapper import from_row
        return [from_row(MapCell, r) for r in rows]

    async def get_by_location(self, location_uid: str) -> list[MapCell]:
        return await self.fetch_all("location_uid = ?", [location_uid])

    async def has_cells_for_location(self, location_uid: str) -> bool:
        sql = "SELECT 1 FROM map_cells WHERE location_uid = ? LIMIT 1"
        async with self._db.conn.execute(sql, [location_uid]) as cur:
            row = await cur.fetchone()
        return row is not None

    async def delete_by_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM map_cells WHERE world_uid = ?", [world_uid]
        )
        if not _in_transaction.get():
            await self._db.conn.commit()
