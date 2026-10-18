import dataclasses
import re
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, nullcontext
from typing import TYPE_CHECKING
from dataclasses import dataclass

from app.application.imports.helpers import with_default_created_at, prepare_import_row
from app.application.imports.result import ImportError, ImportResult
from app.application.jsonValidation.facade import normalize_world, merge_world_patch
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldSliceMerge import merge_world_slice
from app.application.jsonValidation.worldSlices import slice_for_pojo, world_wire_from_row
from app.dataModel.worldPack.meta.worldGridSettings import WorldGridSettings
from app.application.worldData.errors import (
    WorldDataError,
    WorldDataNotFoundError,
    WorldDataValidationError,
)
from app.application.worldData.registries.worldColumnWrite import invalidated_world_tables
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository

if TYPE_CHECKING:
    from app.application.worldData.regions.declaredRegionEdit import DeclaredRegionEditor
    from app.dataModel.terrainMasks.regions.edit import DeclaredRegionEdit


@dataclass
class WorldUpdateResult:
    world:                World
    warning:              str | None = None
    requires_force:       bool = False   # True → not saved, client must re-send with force=true
    map_cells_invalidated: bool = False  # True → saved, caller must clear map_cells


class WorldService:

    def __init__(self, repo: IWorldRepository, *, region_editor: "DeclaredRegionEditor | None" = None) -> None:
        self._repo = repo
        self._region_editor = region_editor

    @asynccontextmanager
    async def _write_scope(self):
        if self._region_editor is None:
            yield
        else:
            async with self._region_editor.transaction():
                yield

    async def _save(self, world: World, method: Callable[[World], Awaitable[None]]) -> None:
        async with self._write_scope():
            before = await self._repo.get_by_id(world.world_uid)
            await method(world)
            if self._region_editor is not None:
                await self._region_editor.reconcile(before, world)

    async def edit_region(self, world_uid: str, operation: "DeclaredRegionEdit", *,
                          validate_only: bool = False) -> World:
        from app.application.jsonValidation.worldRow import terrain_masks
        from app.application.worldData.regions.declaredRegionEdit import apply_region_operation
        async with nullcontext() if validate_only else self._write_scope():
            world = await self.get_by_id(world_uid)
            ctx = ResolveContext.for_import(validate_only=validate_only)
            try:
                patch = apply_region_operation(terrain_masks(world), operation,
                    ctx.child("terrain_masks").child("declared_regions"))
            except UnresolvedModelError as exc:
                raise ImportValidationError(list(exc.issues)) from exc
            merged = merge_world_patch(world_wire_from_row(world), patch)
            self.prepare_import(normalize_world(merged, ctx=ctx), ctx=ctx)
            if validate_only:
                return world
            return (await self._update(world_uid, patch)).world

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_all(self) -> list[World]:
        return await self._repo.get_all()

    async def get_by_id(self, world_uid: str) -> World:
        world = await self._repo.get_by_id(world_uid)
        if world is None:
            raise WorldDataNotFoundError(f"World '{world_uid}' not found")
        return world

    async def find_by_id(self, world_uid: str) -> World | None:
        return await self._repo.get_by_id(world_uid)

    async def create(self, data: dict) -> World:
        data = _normalize_world_data(with_default_created_at(data))
        world = self.prepare_import(data)
        await self._save(world, self._repo.create)
        return world

    _IMMUTABLE = frozenset({"world_uid", "created_at"})

    async def update(self, world_uid: str, data: dict) -> WorldUpdateResult:
        async with self._write_scope():
            return await self._update(world_uid, data)

    async def _update(self, world_uid: str, data: dict) -> WorldUpdateResult:
        data = dict(data)
        force = bool(data.pop("force", False))
        data = _normalize_world_data(data, partial=True)
        world = await self.get_by_id(world_uid)
        original = dataclasses.replace(world)  # snapshot before mutations

        patch = {key: value for key, value in data.items()
                 if hasattr(world, key) and key not in self._IMMUTABLE}
        merged = merge_world_patch(world_wire_from_row(world), patch)
        try:
            world = self.prepare_import(_normalize_world_data(merged))
        except WorldDataError:
            raise
        except ValueError as exc:
            raise WorldDataValidationError(str(exc)) from exc

        invalidated = invalidated_world_tables(
            world_wire_from_row(original), world_wire_from_row(world))
        map_cells_invalidated = "map_cells" in invalidated

        if map_cells_invalidated and not force:
            return WorldUpdateResult(
                world=original,
                warning=(
                    f"fine_cells_per_map_cell changed from "
                    f"{original.fine_cells_per_map_cell} to {world.fine_cells_per_map_cell}. "
                    "All map_cells will be deleted and terrain must be regenerated. "
                    "Re-send with force=true to confirm."
                ),
                requires_force=True,
            )

        await self._save(world, self._repo.update)
        return WorldUpdateResult(
            world=world,
            map_cells_invalidated=map_cells_invalidated,
        )

    async def repair_defaults(self, world: World) -> World:
        """Re-apply import ``normalize_world`` defaults and persist if climate liquid missing."""
        from app.application.worldData.registries.repairWorldDefaults import ensure_world_climate_defaults

        return await ensure_world_climate_defaults(world, repo=self._repo)

    async def delete(self, world_uid: str) -> None:
        await self.get_by_id(world_uid)
        await self._repo.delete(world_uid)

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, data: dict) -> ImportResult:
        data = _normalize_world_data(with_default_created_at(data))
        try:
            world = self.prepare_import(data)
            await self._save(world, self._repo.upsert)
            return ImportResult(total=1, succeeded=1, failed=0)
        except WorldDataError:
            raise
        except Exception as e:
            return ImportResult(
                total=1, succeeded=0, failed=1,
                errors=[ImportError(index=0, message=str(e))],
            )

    @classmethod
    def prepare_import(cls, data: dict, *, ctx: ResolveContext | None = None) -> World:
        from app.application.jsonValidation.declaredRegions import validate_declared_regions

        ctx = ctx if ctx is not None else ResolveContext.for_import()
        data = dict(data)
        # Direct preflight callers do not necessarily pass facade-normalized wire.
        # Validate the authored mapping before SQL projection can omit explicit null.
        grid_slice = slice_for_pojo(WorldGridSettings)
        assert grid_slice is not None
        try:
            merge_world_slice(data, grid_slice, ctx)
        except UnresolvedModelError as exc:
            raise ImportValidationError(list(exc.issues)) from exc
        world = prepare_import_row(World, with_default_created_at(data))
        cls._validate(world)
        try:
            validate_declared_regions(world, ctx)
        except UnresolvedModelError as exc:
            raise ImportValidationError(list(exc.issues)) from exc
        if ctx.errors:
            raise ImportValidationError(list(ctx.errors))
        return world

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
        if world.grid_bbox_padding < 0:
            raise WorldDataValidationError(
                "grid_bbox_padding must be >= 0")

        chunk = world.terrain_chunk_columns
        if not isinstance(chunk, int) or isinstance(chunk, bool) or chunk < 1:
            raise WorldDataValidationError(
                "terrain_chunk_columns must be an integer >= 1")

        depth = world.map_subsurface_depth
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
            raise WorldDataValidationError(
                "map_subsurface_depth must be an integer >= 0")


def _normalize_world_data(data: dict, *, partial: bool = False) -> dict:
    return normalize_world(data, partial=partial)
