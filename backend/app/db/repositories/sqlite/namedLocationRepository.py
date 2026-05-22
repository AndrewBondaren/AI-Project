from app.db.database import Database
from app.db.models.named_location import NamedLocation
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteNamedLocationRepository(BaseRepository[NamedLocation], INamedLocationRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, NamedLocation)

    async def get_by_id(self, location_uid: str) -> NamedLocation | None:
        return await self.fetch_one("location_uid = ?", [location_uid])

    async def get_by_world(self, world_uid: str) -> list[NamedLocation]:
        return await self.fetch_all("world_uid = ?", [world_uid], order="display_name ASC")

    async def get_children(self, parent_uid: str) -> list[NamedLocation]:
        return await self.fetch_all("parent_location_uid = ?", [parent_uid], order="display_name ASC")

    async def create(self, loc: NamedLocation) -> None:
        await self.insert(loc)

    async def update(self, loc: NamedLocation) -> None:
        await self.save(loc)

    async def upsert(self, loc: NamedLocation) -> None:
        await super().upsert(loc)

    async def delete(self, location_uid: str) -> None:
        await super().delete(location_uid)
