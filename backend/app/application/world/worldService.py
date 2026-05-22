from fastapi import HTTPException

from app.api.schemas.imports import ImportError, ImportResult
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


class WorldService:

    def __init__(self, repo: IWorldRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self) -> list[World]:
        return await self._repo.get_all()

    async def get_by_id(self, world_id: str) -> World:
        world = await self._repo.get_by_id(world_id)
        if world is None:
            raise HTTPException(status_code=404, detail=f"World '{world_id}' not found")
        return world

    async def create(self, data: dict) -> World:
        world = World(**data)
        await self._repo.create(world)
        return world

    _IMMUTABLE = frozenset({"id", "created_at"})

    async def update(self, world_id: str, data: dict) -> World:
        world = await self.get_by_id(world_id)
        for key, value in data.items():
            if hasattr(world, key) and key not in self._IMMUTABLE:
                setattr(world, key, value)
        await self._repo.update(world)
        return world

    async def delete(self, world_id: str) -> None:
        await self.get_by_id(world_id)
        await self._repo.delete(world_id)

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, data: dict) -> ImportResult:
        try:
            world = World(**data)
            await self._repo.upsert(world)
            return ImportResult(total=1, succeeded=1, failed=0)
        except Exception as e:
            return ImportResult(
                total=1, succeeded=0, failed=1,
                errors=[ImportError(index=0, message=str(e))],
            )
