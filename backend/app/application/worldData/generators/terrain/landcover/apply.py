"""Region competition uses the common precedence rule and common terrain writer."""

from functools import partial

from app.application.worldData.generators.terrain.landcover.types import ResolvedRegion
from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.masks.regionPrecedence import RegionCandidate, compare_region_candidates
from app.application.worldData.masks.terrainMerge import PRESERVE_HYDROLOGY_ROLES, may_paint_terrain, terrain_merge_rank
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


def apply_region(compose: LightGridCompose, footprint: MaskFootprint, region: ResolvedRegion,
                 registry: WorldTerrainRegistry, winners: dict[LightCellRef, RegionCandidate],
                 tile_set: set[tuple[int, int]]) -> None:
    candidate = RegionCandidate(region.current_type, region.spec, region.region_uid, region.claim_area)
    rank = partial(terrain_merge_rank, registry=registry)
    accepted = set()
    for ref in footprint.cells:
        if (ref.gx, ref.gy) not in tile_set:
            continue
        cell = compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty)
        if cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
            continue
        if not may_paint_terrain(cell.system_terrain, region.current_type, registry):
            continue
        previous = winners.get(ref)
        if previous is not None and compare_region_candidates(candidate, previous, merge_rank=rank) >= 0:
            continue
        accepted.add(ref)
        winners[ref] = candidate
    apply_terrain_footprint(compose, MaskFootprint(frozenset(accepted)),
                            system_terrain=region.current_type, registry=registry,
                            tile_set=tile_set, preserve_hydro=True)
