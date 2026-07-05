from fastapi import HTTPException

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list, with_default_created_at
from app.db.models.namedLocation import NamedLocation
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

    _IMMUTABLE = frozenset({"location_uid", "world_uid"})

    async def create(self, world_uid: str, data: dict) -> NamedLocation:
        loc = NamedLocation(**{**with_default_created_at(data), "world_uid": world_uid})
        await self._repo.create(loc)
        return loc

    async def update(self, world_uid: str, location_uid: str, data: dict) -> NamedLocation:
        loc = await self.get_by_id(world_uid, location_uid)
        for key, value in data.items():
            if hasattr(loc, key) and key not in self._IMMUTABLE:
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
        def prepare(row: dict) -> NamedLocation:
            return NamedLocation(**{**with_default_created_at(row), "world_uid": world_uid})
        return await import_list(data, prepare, self._repo.upsert, id_key="location_uid")
