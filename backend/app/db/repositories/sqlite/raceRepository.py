from app.db.database import Database
from app.db.models.race import Race
from app.db.repositories.iRaceRepository import IRaceRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteRaceRepository(BaseRepository[Race], IRaceRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, Race)

    async def get_by_id(self, race_uid: str) -> Race | None:
        return await self.fetch_one("race_uid = ?", [race_uid])

    async def get_by_world(self, world_uid: str) -> list[Race]:
        return await self.fetch_all("world_uid = ?", [world_uid], order="display_race ASC")

    async def create(self, race: Race) -> None:
        await self.insert(race)

    async def update(self, race: Race) -> None:
        await self.save(race)

    async def upsert(self, race: Race) -> None:
        await super().upsert(race)

    async def delete(self, race_uid: str) -> None:
        await super().delete(race_uid)
