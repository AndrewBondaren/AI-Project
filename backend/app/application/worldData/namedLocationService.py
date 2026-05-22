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

    async def get_all(self, world_uid: str) -> list[NamedLocation]:
        return await self._repo.get_by_world(world_uid)

    async def get_by_id(self, world_uid: str, location_uid: str) -> NamedLocation:
        loc = await self._repo.get_by_id(location_uid)
        if loc is None or loc.world_uid != world_uid:
            raise HTTPException(status_code=404, detail=f"Location '{location_uid}' not found")
        return loc

    async def get_children(self, world_uid: str, parent_uid: str) -> list[NamedLocation]:
        await self.get_by_id(world_uid, parent_uid)
        return await self._repo.get_children(parent_uid)

    async def create(self, world_uid: str, data: dict) -> NamedLocation:
        data["world_uid"] = world_uid
        loc = NamedLocation(**data)
        await self._repo.create(loc)
        return loc

    async def update(self, world_uid: str, location_uid: str, data: dict) -> NamedLocation:
        loc = await self.get_by_id(world_uid, location_uid)
        for key, value in data.items():
            if hasattr(loc, key) and key not in ("location_uid", "world_uid"):
                setattr(loc, key, value)
        await self._repo.update(loc)
        return loc

    async def delete(self, world_uid: str, location_uid: str) -> None:
        await self.get_by_id(world_uid, location_uid)
        await self._repo.delete(location_uid)

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        total = len(data)
        succeeded = 0
        errors: list[ImportError] = []

        for i, row in enumerate(data):
            try:
                row["world_uid"] = world_uid
                loc = NamedLocation(**row)
                await self._repo.upsert(loc)
                succeeded += 1
            except Exception as e:
                errors.append(ImportError(index=i, message=str(e)))

        return ImportResult(total=total, succeeded=succeeded, failed=len(errors), errors=errors)
