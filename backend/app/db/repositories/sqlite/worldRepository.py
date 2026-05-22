from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteWorldRepository(BaseRepository[World], IWorldRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, World)

    async def get_by_id(self, world_id: str) -> World | None:
        return await self.fetch_one("id = ?", [world_id])

    async def get_all(self) -> list[World]:
        return await self.fetch_all(order="created_at DESC")

    async def create(self, world: World) -> None:
        await self.insert(world)

    async def update(self, world: World) -> None:
        await self.save(world)

    async def upsert(self, world: World) -> None:
        await super().upsert(world)

    async def delete(self, world_id: str) -> None:
        await super().delete(world_id)

    async def increment_tick(self, world_id: str) -> int:
        await self._db.conn.execute(
            "UPDATE worlds SET current_tick = current_tick + 1 WHERE id = ?",
            (world_id,),
        )
        await self._db.conn.commit()
        async with self._db.conn.execute(
            "SELECT current_tick FROM worlds WHERE id = ?", (world_id,)
        ) as cur:
            row = await cur.fetchone()
        return row["current_tick"]
