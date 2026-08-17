"""Shore terrain/material from category hydrology POJO — D HY-2 / U15."""

from __future__ import annotations

from collections import deque
from typing import Any, Mapping

from app.application.jsonValidation.worldRow import hydrology
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain

_INFER_BFS_LIMIT = 256

_KIND_TERRAIN: dict[HydrologyShoreKind, ReliefConditionTerrain] = {
    HydrologyShoreKind.RIVER: ReliefConditionTerrain.SHORE_RIVER,
    HydrologyShoreKind.MOUNTAIN_RIVER: ReliefConditionTerrain.SHORE_MOUNTAIN_RIVER,
    HydrologyShoreKind.LAKE: ReliefConditionTerrain.SHORE_LAKE,
    HydrologyShoreKind.SEA: ReliefConditionTerrain.SHORE_SEA,
}

_OPEN_SEA_ROLES = frozenset({
    HydrologyCellRole.COASTAL_SEA,
    HydrologyCellRole.OPEN_OCEAN,
    HydrologyCellRole.INLAND_SEA,
})


def _as_defaults(shore: Any) -> HydrologyShoreDefaults:
    if isinstance(shore, HydrologyShoreDefaults):
        return shore
    if isinstance(shore, dict):
        return HydrologyShoreDefaults.model_validate(shore)
    return HydrologyShoreDefaults.model_validate(shore)


def shore_defaults_for(world: Any, kind: HydrologyShoreKind) -> HydrologyShoreDefaults:
    """Paint pair from ``default_<category>.shore`` / ``mountain_shore`` — not ``default_shore``."""
    policy = hydrology(world)
    if kind is HydrologyShoreKind.RIVER:
        return _as_defaults(policy.default_rivers.shore)
    if kind is HydrologyShoreKind.MOUNTAIN_RIVER:
        return _as_defaults(policy.default_rivers.mountain_shore)
    if kind is HydrologyShoreKind.LAKE:
        return _as_defaults(policy.default_lakes.shore)
    return _as_defaults(policy.default_seas.shore)


def shore_terrain_material(
    world: Any,
    kind: HydrologyShoreKind,
) -> tuple[str, str]:
    shore = shore_defaults_for(world, kind)
    fallback = _KIND_TERRAIN[kind]
    terrain = str(shore.system_terrain or "").strip()
    if not terrain or terrain == "shore":
        terrain = fallback.value
    material = str(shore.system_material or "").strip()
    if not material:
        material = HydrologyShoreDefaults.for_condition(fallback).system_material
    return terrain, material


def infer_shore_kind(
    xy: tuple[int, int],
    by_cell: Mapping[tuple[int, int], MapCellHydrology],
) -> HydrologyShoreKind | None:
    """Nearest water / river_bed / stamped shore through contiguous ``role=shore``."""
    start = by_cell.get(xy)
    if start is not None and start.shore_kind is not None:
        return start.shore_kind
    seen: set[tuple[int, int]] = {xy}
    queue: deque[tuple[int, int]] = deque([xy])
    steps = 0
    while queue and steps < _INFER_BFS_LIMIT:
        cx, cy = queue.popleft()
        steps += 1
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            nb = (nx, ny)
            if nb in seen:
                continue
            entry = by_cell.get(nb)
            if entry is None or entry.role is None:
                continue
            seen.add(nb)
            if entry.shore_kind is not None:
                return entry.shore_kind
            if entry.role in _OPEN_SEA_ROLES:
                return HydrologyShoreKind.SEA
            if entry.role is HydrologyCellRole.LAKE:
                return HydrologyShoreKind.LAKE
            if entry.role is HydrologyCellRole.RIVER_BED:
                return HydrologyShoreKind.RIVER
            if entry.role is HydrologyCellRole.SHORE:
                queue.append(nb)
    return None


def apply_shore_surface(
    role: HydrologyCellRole | None,
    z: int,
    terrain_set: set[str],
    default_terrain: str,
    *,
    shore_terrain: str,
) -> str:
    """Surface terrain for hydrology shore roles; open water stays on elevation mapping."""
    if role != HydrologyCellRole.SHORE:
        return default_terrain
    if shore_terrain in terrain_set:
        return shore_terrain
    try:
        if ReliefConditionTerrain(shore_terrain).is_shore_class():
            return shore_terrain
    except ValueError:
        return default_terrain
    return default_terrain
