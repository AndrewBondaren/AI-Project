"""RELIEF-BAR-1: Intent ``structure_refs`` → light-grid ``wall`` along ribbon.

Outside ``generators/terrain/relief``. Clearance: no road / grade / pin / hydro /
existing wall (same spirit as R36m — do not overwrite footprints).
Light wire has no ``system_material`` — material resolved for log/RNG only.
"""

from __future__ import annotations

from collections.abc import Callable
from random import Random

from app.application.jsonValidation import terrain_masks
from app.application.jsonValidation.worldRow import barrier_templates
from app.application.worldData.generators.barrier.material import pick_barrier_material
from app.application.worldData.generators.barrier.ribbonFence import fence_cells_along_ribbon
from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_R21_FALLBACK,
    EVENT_ROAD_SHOULDER_BARRIER,
    WHY_EMPTY_FENCE_FOOTPRINT,
    WHY_NO_BARRIER_REFS,
    WHY_UNKNOWN_BARRIER_REF,
)
from app.application.worldData.generators.terrain.relief.reliefLog import (
    relief_debug,
    relief_warning,
)
from app.application.worldData.masks.terrainMerge import PRESERVE_HYDROLOGY_ROLES
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_to_macro_local
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderStamp import (
    cell_blocked_light,
)
from app.application.worldData.pack.bake.lightGrid.roadShoulderIntent import (
    RoadShoulderIntent,
)
from app.dataModel.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

# Stamp / obstacle SoT = terrain_registry (engine barrier category), not string literals.
_BARRIER_TERRAIN = WorldTerrainRegistry.require_engine_terrain_key("wall")
_EXISTING_BARRIER = WorldTerrainRegistry.canonical_barrier_terrain_keys()


def apply_road_shoulder_barriers(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
) -> int:
    """Stamp fence cells for all non-skipped intents with resolved barrier refs."""
    tile_set = set(ctx.tiles)
    if not tile_set or not ctx.road_shoulder_intents:
        return 0
    masks = terrain_masks(ctx.world)
    road_key = masks.default_roads.system_terrain
    registry = barrier_templates(ctx.world)
    world_seed = bake_seed(ctx.world)
    painted = 0
    for intent in ctx.road_shoulder_intents:
        painted += _apply_intent_barriers(
            compose,
            intent,
            tile_set=tile_set,
            road_key=road_key,
            registry_entry_for=registry.entry_for,
            world_seed=world_seed,
            world=ctx.world,
        )
    relief_debug(
        EVENT_ROAD_SHOULDER_BARRIER,
        intents=len(ctx.road_shoulder_intents),
        cells_painted=painted,
    )
    return painted


def _apply_intent_barriers(
    compose: LightGridCompose,
    intent: RoadShoulderIntent,
    *,
    tile_set: set[tuple[int, int]],
    road_key: str,
    registry_entry_for: Callable[[str], BarrierTemplateEntry | None],
    world_seed: str,
    world,
) -> int:
    if intent.skipped or not intent.cell_coords:
        return 0
    refs = intent.structure_refs
    if not refs:
        return 0
    entries: list[BarrierTemplateEntry] = []
    for ref in refs:
        entry = registry_entry_for(ref)
        if entry is None:
            relief_warning(
                EVENT_R21_FALLBACK,
                site_id=intent.site_id,
                why=WHY_UNKNOWN_BARRIER_REF,
                ref=ref,
            )
            continue
        entries.append(entry)
    if not entries:
        relief_debug(
            EVENT_ROAD_SHOULDER_BARRIER,
            site_id=intent.site_id,
            why=WHY_NO_BARRIER_REFS,
            refs=list(refs),
        )
        return 0

    grade = set(intent.cell_coords)

    def allow(cell: tuple[int, int]) -> bool:
        return _may_place_fence(
            compose,
            cell,
            tile_set=tile_set,
            grade=grade,
            road_key=road_key,
        )

    footprint = fence_cells_along_ribbon(grade, allow=allow)
    if not footprint:
        relief_debug(
            EVENT_ROAD_SHOULDER_BARRIER,
            site_id=intent.site_id,
            why=WHY_EMPTY_FENCE_FOOTPRINT,
            grade_cells=len(grade),
        )
        return 0

    # Material for observability (light wire has no system_material yet).
    rng = Random(f"{world_seed}:barrier:{intent.site_id}")
    material = pick_barrier_material(world, entries[0], economic_tier=None, rng=rng)
    n = _stamp_wall_cells(compose, footprint, tile_set=tile_set)
    relief_debug(
        EVENT_ROAD_SHOULDER_BARRIER,
        site_id=intent.site_id,
        refs=[e.system_type for e in entries],
        material=material,
        cells=n,
    )
    return n


def _may_place_fence(
    compose: LightGridCompose,
    cell: tuple[int, int],
    *,
    tile_set: set[tuple[int, int]],
    grade: set[tuple[int, int]],
    road_key: str,
) -> bool:
    if cell in grade:
        return False
    if cell_blocked_light(compose, cell, tile_set=tile_set):
        return False
    lx, ly = cell
    gx, gy, tx, ty = light_to_macro_local(lx, ly, compose.scale)
    grid = compose.get(gx, gy, tx, ty)
    if grid is None:
        return False
    if grid.system_terrain == road_key:
        return False
    if grid.system_terrain in _EXISTING_BARRIER:
        return False
    if grid.system_grade_uid:
        return False
    if grid.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
        return False
    return True


def _stamp_wall_cells(
    compose: LightGridCompose,
    cells: set[tuple[int, int]],
    *,
    tile_set: set[tuple[int, int]],
) -> int:
    """Force ``wall`` — barrier is not a MaskDomain (no merge-rank entry)."""
    scale = compose.scale
    painted = 0
    for lx, ly in sorted(cells):
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        if not (0 <= tx < scale.side and 0 <= ty < scale.side):
            continue
        cell = compose.ensure(gx, gy, tx, ty)
        if cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
            continue
        if cell.system_grade_uid or cell.location_pin is not None:
            continue
        cell.system_terrain = _BARRIER_TERRAIN
        painted += 1
    return painted
