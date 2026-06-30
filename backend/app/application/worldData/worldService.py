import dataclasses
import re
from dataclasses import dataclass

from fastapi import HTTPException

from app.api.schemas.imports import ImportError, ImportResult
from app.application.worldData.jsonValidation.validators.worldRow import (
    collect_world_row_issues_from_world,
)
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


@dataclass
class WorldUpdateResult:
    world:                World
    warning:              str | None = None
    requires_force:       bool = False   # True → not saved, client must re-send with force=true
    map_cells_invalidated: bool = False  # True → saved, caller must clear map_cells


class WorldService:

    def __init__(self, repo: IWorldRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self) -> list[World]:
        return await self._repo.get_all()

    async def get_by_id(self, world_uid: str) -> World:
        world = await self._repo.get_by_id(world_uid)
        if world is None:
            raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
        return world

    async def find_by_id(self, world_uid: str) -> World | None:
        return await self._repo.get_by_id(world_uid)

    async def create(self, data: dict) -> World:
        world = World(**data)
        await self._repo.create(world)
        return world

    _IMMUTABLE = frozenset({"world_uid", "created_at"})

    async def update(self, world_uid: str, data: dict) -> WorldUpdateResult:
        force = bool(data.pop("force", False))
        world = await self.get_by_id(world_uid)
        original = dataclasses.replace(world)  # snapshot before mutations
        old_map_cell_size = world.map_cell_size_m

        for key, value in data.items():
            if hasattr(world, key) and key not in self._IMMUTABLE:
                setattr(world, key, value)

        map_size_changed = old_map_cell_size != world.map_cell_size_m

        if map_size_changed and not force:
            return WorldUpdateResult(
                world=original,
                warning=(
                    f"map_cell_size_m changed from {old_map_cell_size} to {world.map_cell_size_m}. "
                    "All map_cells will be deleted and terrain must be regenerated. "
                    "Re-send with force=true to confirm."
                ),
                requires_force=True,
            )

        await self._repo.update(world)
        return WorldUpdateResult(
            world=world,
            map_cells_invalidated=map_size_changed,
        )

    async def delete(self, world_uid: str) -> None:
        await self.get_by_id(world_uid)
        await self._repo.delete(world_uid)

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, data: dict) -> ImportResult:
        try:
            world = World(**data)
            self._validate(world)
            await self._repo.upsert(world)
            return ImportResult(total=1, succeeded=1, failed=0)
        except HTTPException as e:
            return ImportResult(
                total=1, succeeded=0, failed=1,
                errors=[ImportError(index=0, message=e.detail)],
            )
        except Exception as e:
            return ImportResult(
                total=1, succeeded=0, failed=1,
                errors=[ImportError(index=0, message=str(e))],
            )

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    async def next_version_number(self, base_name: str) -> int:
        """Return the next version number for a world family identified by base_name.
        Finds the highest existing vN suffix and adds 1, so gaps are handled correctly:
        v1 + v3 (v2 deleted) → next is v4. Original (no suffix) → first copy is v1.
        """
        base = self.strip_version_suffix(base_name)
        max_v = 0
        for w in await self._repo.get_all():
            m = re.match(rf'^{re.escape(base)} v(\d+)$', w.name)
            if m:
                max_v = max(max_v, int(m.group(1)))
        return max_v + 1

    @staticmethod
    def strip_version_suffix(name: str) -> str:
        """'Эйдора v3' → 'Эйдора'"""
        return re.sub(r'\s+v\d+$', '', name).strip()

    # ------------------------------------------------------------------

    @staticmethod
    def _validate(world: World) -> None:
        issues = collect_world_row_issues_from_world(world)
        if issues:
            raise HTTPException(status_code=422, detail=issues[0].message)
