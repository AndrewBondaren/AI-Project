from fastapi import HTTPException

from app.api.schemas.imports import ImportError, ImportResult
from app.db.models.world_perk import WorldPerk
from app.db.repositories.iWorldPerkRepository import IWorldPerkRepository


class WorldPerkService:

    def __init__(self, repo: IWorldPerkRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self, world_id: str) -> list[WorldPerk]:
        return await self._repo.get_by_world(world_id)

    async def get_by_id(self, world_id: str, perk_uid: str) -> WorldPerk:
        perk = await self._repo.get_by_id(perk_uid)
        if perk is None or perk.world_id != world_id:
            raise HTTPException(status_code=404, detail=f"Perk '{perk_uid}' not found")
        return perk

    async def create(self, world_id: str, data: dict) -> WorldPerk:
        data["world_id"] = world_id
        perk = WorldPerk(**data)
        await self._repo.create(perk)
        return perk

    async def update(self, world_id: str, perk_uid: str, data: dict) -> WorldPerk:
        perk = await self.get_by_id(world_id, perk_uid)
        for key, value in data.items():
            if hasattr(perk, key) and key not in ("perk_uid", "world_id"):
                setattr(perk, key, value)
        await self._repo.update(perk)
        return perk

    async def delete(self, world_id: str, perk_uid: str) -> None:
        await self.get_by_id(world_id, perk_uid)
        await self._repo.delete(perk_uid)

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
                perk = WorldPerk(**row)
                await self._repo.upsert(perk)
                succeeded += 1
            except Exception as e:
                errors.append(ImportError(index=i, message=str(e)))

        return ImportResult(total=total, succeeded=succeeded, failed=len(errors), errors=errors)
