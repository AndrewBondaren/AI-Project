from fastapi import HTTPException

from app.api.schemas.imports import ImportError, ImportResult
from app.db.models.named_location import NamedLocation
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository


class NamedLocationService:

    def __init__(self, repo: INamedLocationRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self, world_id: str) -> list[NamedLocation]:
        return await self._repo.get_by_world(world_id)

    async def get_by_id(self, world_id: str, location_uid: str) -> NamedLocation:
        loc = await self._repo.get_by_id(location_uid)
        if loc is None or loc.world_id != world_id:
            raise HTTPException(status_code=404, detail=f"Location '{location_uid}' not found")
        return loc

    async def get_children(self, world_id: str, parent_uid: str) -> list[NamedLocation]:
        await self.get_by_id(world_id, parent_uid)
        return await self._repo.get_children(parent_uid)

    async def create(self, world_id: str, data: dict) -> NamedLocation:
        data["world_id"] = world_id
        loc = NamedLocation(**data)
        await self._repo.create(loc)
        return loc

    async def update(self, world_id: str, location_uid: str, data: dict) -> NamedLocation:
        loc = await self.get_by_id(world_id, location_uid)
        for key, value in data.items():
            if hasattr(loc, key) and key not in ("location_uid", "world_id"):
                setattr(loc, key, value)
        await self._repo.update(loc)
        return loc

    async def delete(self, world_id: str, location_uid: str) -> None:
        await self.get_by_id(world_id, location_uid)
        await self._repo.delete(location_uid)

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
                loc = NamedLocation(**row)
                await self._repo.upsert(loc)
                succeeded += 1
            except Exception as e:
                errors.append(ImportError(index=i, message=str(e)))

        return ImportResult(total=total, succeeded=succeeded, failed=len(errors), errors=errors)
