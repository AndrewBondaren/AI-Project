"""RELIEF-BAR-1: Intent ``structure_refs`` → light-grid barrier along ribbon.

Outside ``generators/terrain/relief``. Placement predicate once → write-only stamp.
Light wire has no ``system_material`` — material = log/RNG from **first** resolved ref.

v1 multi-ref: union one footprint; stamp once; unknown refs warn+skip individually.
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
    EVENT_RESOLVE_FALLBACK,
    EVENT_RIBBON_BARRIER,
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
from app.application.worldData.pack.bake.lightGrid.paintBarrier import stamp_barrier_terrain
from app.application.worldData.pack.bake.lightGrid.ribbonIntent import RibbonIntent
from app.dataModel.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.db.models.world import World

_BARRIER_TERRAIN = WorldTerrainRegistry.require_engine_terrain_key("wall")


def apply_ribbon_barriers(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
) -> int:
    """Stamp fence cells for all non-skipped intents with resolved barrier refs."""
    tile_set = set(ctx.tiles)
    if not tile_set or not ctx.ribbon_intents:
        return 0
    masks = terrain_masks(ctx.world)
    road_key = masks.default_roads.system_terrain
    registry = barrier_templates(ctx.world)
    world_seed = bake_seed(ctx.world)
    painted = 0
    for intent in ctx.ribbon_intents:
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
        EVENT_RIBBON_BARRIER,
        intents=len(ctx.ribbon_intents),
        cells_painted=painted,
    )
    return painted


def _apply_intent_barriers(
    compose: LightGridCompose,
    intent: RibbonIntent,
    *,
    tile_set: set[tuple[int, int]],
    road_key: str,
    registry_entry_for: Callable[[str], BarrierTemplateEntry | None],
    world_seed: str,
    world: World,
) -> int:
    if intent.skipped or not intent.cell_coords:
        return 0
    entries = _resolve_barrier_entries(
        intent.structure_refs,
        registry_entry_for=registry_entry_for,
        site_id=intent.site_id,
    )
    if not entries:
        return 0

    grade = set(intent.cell_coords)
    footprint = fence_cells_along_ribbon(
        grade,
        allow=lambda c: _may_place_fence(
            compose, c, tile_set=tile_set, grade=grade, road_key=road_key,
        ),
    )
    if not footprint:
        relief_debug(
            EVENT_RIBBON_BARRIER,
            site_id=intent.site_id,
            why=WHY_EMPTY_FENCE_FOOTPRINT,
            grade_cells=len(grade),
        )
        return 0

    # v1: one footprint; material from first resolved ref (wire has no system_material).
    rng = Random(f"{world_seed}:barrier:{intent.site_id}")
    material = pick_barrier_material(world, entries[0], economic_tier=None, rng=rng)
    n = stamp_barrier_terrain(
        compose, footprint, _BARRIER_TERRAIN, tile_set=tile_set,
    )
    relief_debug(
        EVENT_RIBBON_BARRIER,
        site_id=intent.site_id,
        refs=[e.system_type for e in entries],
        material=material,
        cells=n,
    )
    return n


def _resolve_barrier_entries(
    refs: tuple[str, ...],
    *,
    registry_entry_for: Callable[[str], BarrierTemplateEntry | None],
    site_id: str,
) -> list[BarrierTemplateEntry]:
    if not refs:
        return []
    entries: list[BarrierTemplateEntry] = []
    for ref in refs:
        entry = registry_entry_for(ref)
        if entry is None:
            relief_warning(
                EVENT_RESOLVE_FALLBACK,
                site_id=site_id,
                why=WHY_UNKNOWN_BARRIER_REF,
                ref=ref,
            )
            continue
        entries.append(entry)
    if not entries:
        relief_debug(
            EVENT_RIBBON_BARRIER,
            site_id=site_id,
            why=WHY_NO_BARRIER_REFS,
            refs=list(refs),
        )
    return entries


def _may_place_fence(
    compose: LightGridCompose,
    cell: tuple[int, int],
    *,
    tile_set: set[tuple[int, int]],
    grade: set[tuple[int, int]],
    road_key: str,
) -> bool:
    """Single placement gate (R36m spirit). Stamp does not re-check."""
    if cell in grade:
        return False
    # pin / OOB / missing / terrain_category=barrier
    if cell_blocked_light(compose, cell, tile_set=tile_set):
        return False
    lx, ly = cell
    gx, gy, tx, ty = light_to_macro_local(lx, ly, compose.scale)
    grid = compose.get(gx, gy, tx, ty)
    if grid is None:
        return False
    if grid.system_terrain == road_key:
        return False
    if grid.system_grade_uid:
        return False
    if grid.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
        return False
    return True
