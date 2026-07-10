import dataclasses
import re
from dataclasses import dataclass

from fastapi import HTTPException

from app.api.schemas.imports import ImportError, ImportResult
from app.application.import_helpers import with_default_created_at
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError, import_validation_http_detail
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
        data = _normalize_world_data(with_default_created_at(data))
        world = World(**data)
        self._validate(world)
        await self._repo.create(world)
        return world

    _IMMUTABLE = frozenset({"world_uid", "created_at"})

    async def update(self, world_uid: str, data: dict) -> WorldUpdateResult:
        force = bool(data.pop("force", False))
        data = _normalize_world_data(data, partial=True)
        world = await self.get_by_id(world_uid)
        original = dataclasses.replace(world)  # snapshot before mutations
        old_map_cell_size = world.map_cell_size_m

        for key, value in data.items():
            if hasattr(world, key) and key not in self._IMMUTABLE:
                setattr(world, key, value)

        self._validate(world)

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
        data = _normalize_world_data(with_default_created_at(data))
        try:
            world = World(**data)
            self._validate(world)
            await self._repo.upsert(world)
            return ImportResult(total=1, succeeded=1, failed=0)
        except HTTPException:
            raise
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
        v = world.map_cell_size_m
        if not isinstance(v, int) or isinstance(v, bool):
            raise HTTPException(status_code=422,
                detail="map_cell_size_m must be an integer")
        if v < 1000:
            raise HTTPException(status_code=422,
                detail="map_cell_size_m must be at least 1000")
        if v % 1000 != 0:
            raise HTTPException(status_code=422,
                detail="map_cell_size_m must be a multiple of 1000")

        if world.grid_bbox_padding < 0:
            raise HTTPException(status_code=422,
                detail="grid_bbox_padding must be >= 0")

        chunk = world.terrain_chunk_columns
        if not isinstance(chunk, int) or isinstance(chunk, bool) or chunk < 1:
            raise HTTPException(status_code=422,
                detail="terrain_chunk_columns must be an integer >= 1")

        depth = world.map_subsurface_depth
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
            raise HTTPException(status_code=422,
                detail="map_subsurface_depth must be an integer >= 0")


def _normalize_world_data(data: dict, *, partial: bool = False) -> dict:
    try:
        return normalize_world(data, partial=partial)
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=import_validation_http_detail(exc)) from exc
