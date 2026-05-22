from fastapi import HTTPException

from app.api.schemas.imports import ImportError, ImportResult
from app.db.models.race import Race
from app.db.repositories.iRaceRepository import IRaceRepository


class RaceService:

    def __init__(self, repo: IRaceRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self, world_id: str) -> list[Race]:
        return await self._repo.get_by_world(world_id)

    async def get_by_id(self, world_id: str, race_uid: str) -> Race:
        race = await self._repo.get_by_id(race_uid)
        if race is None or race.world_id != world_id:
            raise HTTPException(status_code=404, detail=f"Race '{race_uid}' not found")
        return race

    async def create(self, world_id: str, data: dict) -> Race:
        data["world_id"] = world_id
        race = Race(**data)
        await self._repo.create(race)
        return race

    async def update(self, world_id: str, race_uid: str, data: dict) -> Race:
        race = await self.get_by_id(world_id, race_uid)
        for key, value in data.items():
            if hasattr(race, key) and key not in ("race_uid", "world_id"):
                setattr(race, key, value)
        await self._repo.update(race)
        return race

    async def delete(self, world_id: str, race_uid: str) -> None:
        await self.get_by_id(world_id, race_uid)
        await self._repo.delete(race_uid)

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, world_id: str, data: list[dict]) -> ImportResult:
        total = len(data)
        succeeded = 0
        errors: list[ImportError] = []

        for i, row in enumerate(data):
            try:
                row["world_id"] = world_id
                race = Race(**row)
                await self._repo.upsert(race)
                succeeded += 1
            except Exception as e:
                errors.append(ImportError(index=i, message=str(e)))

        return ImportResult(total=total, succeeded=succeeded, failed=len(errors), errors=errors)
