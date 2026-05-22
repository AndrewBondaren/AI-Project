from app.db.database import Database
from app.db.models.world_perk import WorldPerk
from app.db.repositories.iWorldPerkRepository import IWorldPerkRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteWorldPerkRepository(BaseRepository[WorldPerk], IWorldPerkRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, WorldPerk)

    async def get_by_id(self, perk_uid: str) -> WorldPerk | None:
        return await self.fetch_one("perk_uid = ?", [perk_uid])

    async def get_by_world(self, world_id: str) -> list[WorldPerk]:
        return await self.fetch_all("world_id = ?", [world_id], order="display_name ASC")

    async def create(self, perk: WorldPerk) -> None:
        await self.insert(perk)

    async def update(self, perk: WorldPerk) -> None:
        await self.save(perk)

    async def upsert(self, perk: WorldPerk) -> None:
        await super().upsert(perk)

    async def delete(self, perk_uid: str) -> None:
        await super().delete(perk_uid)
