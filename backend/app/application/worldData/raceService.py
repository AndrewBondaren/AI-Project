from fastapi import HTTPException

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list, with_default_created_at
from app.db.models.race import Race
from app.db.repositories.iRaceRepository import IRaceRepository


class RaceService:

    def __init__(self, repo: IRaceRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self, world_uid: str) -> list[Race]:
        return await self._repo.get_by_world(world_uid)

    async def get_by_id(self, world_uid: str, race_uid: str) -> Race:
        race = await self._repo.get_by_id(race_uid)
        if race is None or race.world_uid != world_uid:
            raise HTTPException(status_code=404, detail=f"Race '{race_uid}' not found")
        return race

    _IMMUTABLE = frozenset({"race_uid", "world_uid"})

    async def create(self, world_uid: str, data: dict) -> Race:
        race = Race(**{**with_default_created_at(data), "world_uid": world_uid})
        await self._repo.create(race)
        return race

    async def update(self, world_uid: str, race_uid: str, data: dict) -> Race:
        race = await self.get_by_id(world_uid, race_uid)
        for key, value in data.items():
            if hasattr(race, key) and key not in self._IMMUTABLE:
                setattr(race, key, value)
        await self._repo.update(race)
        return race

    async def delete(self, world_uid: str, race_uid: str) -> None:
        await self.get_by_id(world_uid, race_uid)
        await self._repo.delete(race_uid)

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        def prepare(row: dict) -> Race:
            return Race(**{**with_default_created_at(row), "world_uid": world_uid})
        return await import_list(data, prepare, self._repo.upsert, id_key="race_uid")
