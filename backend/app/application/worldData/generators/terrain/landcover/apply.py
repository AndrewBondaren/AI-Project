"""Region competition uses the common precedence rule and common terrain writer."""

from app.application.worldData.generators.terrain.landcover.types import ResolvedRegion
from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.masks.regionPrecedence import RegionCandidate
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


def apply_region(compose: LightGridCompose, footprint: MaskFootprint, region: ResolvedRegion,
                 registry: WorldTerrainRegistry, winners: dict[LightCellRef, RegionCandidate],
                 tile_set: set[tuple[int, int]]) -> None:
    candidate = RegionCandidate(region.current_type, region.spec, region.region_uid, region.claim_area)
    apply_terrain_footprint(compose, footprint,
                            system_terrain=region.current_type, registry=registry,
                            tile_set=tile_set, preserve_hydro=True, region=candidate, winners=winners)
