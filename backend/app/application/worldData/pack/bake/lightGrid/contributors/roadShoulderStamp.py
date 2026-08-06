"""Light-grid stamp for road_shoulder ribbons — bake only (T-30/T-52 phase 2).

Mutates ``LightGridCompose``; not generators/terrain.
Logging of stamp breaks = materialize (StampRibbonOutcome — T-61).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.edgeRoadAnchor import (
    EdgeRoadAnchor,
)
from app.application.worldData.generators.terrain.relief.facing import (
    facing_wire,
    uphill_facing_toward,
)
from app.application.worldData.generators.terrain.relief.gradeObstacleLight import (
    is_grade_obstacle_light,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    WHY_EMPTY_STAMP,
    WHY_STAMP_COLUMN_FAIL,
    WHY_STAMP_OBSTACLE_BREAK,
)
from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    RibbonVolumePlan,
)
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import (
    light_cell_center_m,
    light_to_macro_local,
)
from app.dataModel.spatial.facing import opposite
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

_BARRIER_TERRAIN_KEYS = WorldTerrainRegistry.canonical_barrier_terrain_keys()


@dataclass(frozen=True, slots=True)
class StampRibbonOutcome:
    """Stamp result without logging — caller owns observability (T-61)."""

    wrote: tuple[tuple[int, int], ...]
    break_why: str | None = None
    break_cell: tuple[int, int] | None = None


def stamp_ribbon_plan(
    compose: LightGridCompose,
    *,
    seed: tuple[int, int],
    plan: RibbonVolumePlan,
    kind: ReliefSideKind,
    sign: int,
    anchor: EdgeRoadAnchor,
    ref_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> StampRibbonOutcome:
    """Write surface_z + facing along outward from seed."""
    dx, dy = anchor.outward
    sx, sy = seed
    wrote: list[tuple[int, int]] = []
    break_why: str | None = None
    break_cell: tuple[int, int] | None = None
    for col in plan.columns:
        lx = sx + dx * (col.k - 1)
        ly = sy + dy * (col.k - 1)
        cell_xy = (lx, ly)
        if _is_obstacle(
            compose, cell_xy, ref_cells=ref_cells, tile_set=tile_set,
        ):
            break_why = WHY_STAMP_OBSTACLE_BREAK
            break_cell = cell_xy
            break
        if not stamp_column(
            compose,
            lx,
            ly,
            surface_z=col.surface_z,
            kind=kind,
            sign=sign,
            anchor=anchor,
            tile_set=tile_set,
        ):
            break_why = WHY_STAMP_COLUMN_FAIL
            break_cell = cell_xy
            break
        wrote.append(cell_xy)
    if break_why is None and plan.columns and not wrote:
        break_why = WHY_EMPTY_STAMP
    return StampRibbonOutcome(
        wrote=tuple(wrote),
        break_why=break_why,
        break_cell=break_cell,
    )


def stamp_grade_uid(
    compose: LightGridCompose,
    cells: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    grade_uid: str,
    *,
    tile_set: set[tuple[int, int]],
) -> None:
    scale = compose.scale
    for lx, ly in cells:
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        cell = compose.get(gx, gy, tx, ty)
        if cell is not None:
            cell.system_grade_uid = grade_uid


def first_column_facing(
    compose: LightGridCompose,
    cell_xy: tuple[int, int],
    *,
    tile_set: set[tuple[int, int]],
) -> str | None:
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(cell_xy[0], cell_xy[1], scale)
    if (gx, gy) not in tile_set:
        return None
    cell = compose.get(gx, gy, tx, ty)
    if cell is None:
        return None
    return cell.system_facing


def stamp_column(
    compose: LightGridCompose,
    lx: int,
    ly: int,
    *,
    surface_z: int,
    kind: ReliefSideKind,
    sign: int,
    anchor: EdgeRoadAnchor,
    tile_set: set[tuple[int, int]],
) -> bool:
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
    if (gx, gy) not in tile_set:
        return False
    cell = compose.get(gx, gy, tx, ty)
    if cell is None:
        return False
    cell.surface_z = int(surface_z)
    if kind is ReliefSideKind.SHEER:
        cell.system_facing = None
        return True
    cx, cy = light_cell_center_m(gx, gy, tx, ty, scale)
    toward_road = uphill_facing_toward(cx, cy, anchor.center_m[0], anchor.center_m[1])
    if toward_road is None:
        cell.system_facing = None
        return True
    facing = toward_road if sign < 0 else opposite(toward_road)
    cell.system_facing = facing_wire(facing)
    return True


def cell_blocked_light(
    compose: LightGridCompose,
    cell: tuple[int, int],
    *,
    tile_set: set[tuple[int, int]],
) -> bool:
    """Bake adapter: OOB / missing / settlement pin / barrier wall (BAR-1)."""
    lx, ly = cell
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
    if (gx, gy) not in tile_set:
        return True
    if not (0 <= tx < scale.side and 0 <= ty < scale.side):
        return True
    grid_cell = compose.get(gx, gy, tx, ty)
    if grid_cell is None:
        return True
    if grid_cell.location_pin is not None:
        return True
    # RELIEF-BAR-1: terrain_category=barrier is a grade obstacle (R36m spirit).
    if grid_cell.system_terrain in _BARRIER_TERRAIN_KEYS:
        return True
    return False


def _is_obstacle(
    compose: LightGridCompose,
    cell: tuple[int, int],
    *,
    ref_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> bool:
    return is_grade_obstacle_light(
        cell,
        ref_cells=ref_cells,
        cell_blocked=lambda c: cell_blocked_light(compose, c, tile_set=tile_set),
    )
