from app.db.database import Database
from app.db.models.world_perk import WorldPerk
from app.db.repositories.iWorldPerkRepository import IWorldPerkRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteWorldPerkRepository(BaseRepository[WorldPerk], IWorldPerkRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, WorldPerk)

    async def get_by_id(self, template_uid: str) -> WorldPerk | None:
        return await self.fetch_one("template_uid = ?", [template_uid])

    async def list_all(self) -> list[WorldPerk]:
        return await self.fetch_all(order="display_name ASC")

    async def get_by_uids(self, uids: list[str]) -> list[WorldPerk]:
        if not uids:
            return []
        placeholders = ",".join("?" * len(uids))
        return await self.fetch_all(
            f"template_uid IN ({placeholders})",
            list(uids),
            order="display_name ASC",
        )

    async def create(self, perk: WorldPerk) -> None:
        await self.insert(perk)

    async def update(self, perk: WorldPerk) -> None:
        await self.save(perk)

    async def upsert(self, perk: WorldPerk) -> None:
        await super().upsert(perk)

    async def delete(self, template_uid: str) -> None:
        await super().delete(template_uid)
