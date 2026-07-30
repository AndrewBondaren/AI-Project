from app.db.database import Database
from app.db.models.race import Race
from app.db.repositories.iRaceRepository import IRaceRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteRaceRepository(BaseRepository[Race], IRaceRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, Race)

    async def get_by_id(self, template_uid: str) -> Race | None:
        return await self.fetch_one("template_uid = ?", [template_uid])

    async def list_all(self) -> list[Race]:
        return await self.fetch_all(order="display_name ASC")

    async def get_by_uids(self, uids: list[str]) -> list[Race]:
        if not uids:
            return []
        placeholders = ",".join("?" * len(uids))
        return await self.fetch_all(
            f"template_uid IN ({placeholders})",
            list(uids),
            order="display_name ASC",
        )

    async def create(self, race: Race) -> None:
        await self.insert(race)

    async def update(self, race: Race) -> None:
        await self.save(race)

    async def upsert(self, race: Race) -> None:
        await super().upsert(race)

    async def delete(self, template_uid: str) -> None:
        await super().delete(template_uid)
