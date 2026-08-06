"""Bake adapters: compose ↔ pure ribbon helpers (RELIEF-T-61).

Kept next to stamp/materialize — not in generators/terrain.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.edgeRoadAnchor import (
    EdgeRoadAnchor,
    edge_road_abutment,
)
from app.application.worldData.generators.terrain.relief.geomResolve import ResolvedGeom
from app.application.worldData.generators.terrain.relief.ribbonSeedResolve import (
    SeedClearance,
)
from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    RibbonVolumePlan,
    geom_for_cleared_length,
    plan_ribbon_volume,
)
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import (
    light_cell_center_m,
    light_to_macro_local,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind


def plan_seed_volume(
    *,
    decision_geom: ResolvedGeom | None,
    h: int,
    kind: ReliefSideKind,
    L_eff: int,
    z_road: int,
    sign: int,
) -> RibbonVolumePlan | None:
    if (
        decision_geom is not None
        and decision_geom.kind is kind
        and int(decision_geom.L) == int(L_eff)
        and int(decision_geom.h) == int(h)
    ):
        geom = decision_geom
    else:
        geom = geom_for_cleared_length(h=h, kind=kind, length=L_eff)
    if geom.L < 1:
        return None
    return plan_ribbon_volume(z_road=z_road, h=h, sign=sign, geom=geom)


def resolve_edge_road_anchor(
    compose: LightGridCompose,
    clearance: SeedClearance,
    *,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> EdgeRoadAnchor | None:
    abutment = edge_road_abutment(
        clearance.seed, clearance.outward, road_cells,
    )
    if abutment is None:
        return None
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(abutment[0], abutment[1], scale)
    if (gx, gy) not in tile_set:
        return None
    cell = compose.get(gx, gy, tx, ty)
    if cell is None:
        return None
    return EdgeRoadAnchor(
        xy=abutment,
        outward=clearance.outward,
        z=int(cell.surface_z),
        center_m=light_cell_center_m(gx, gy, tx, ty, scale),
    )
