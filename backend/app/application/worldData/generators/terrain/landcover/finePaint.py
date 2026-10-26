"""L2 region paint — tz_map_light_bake § Регионы покрытия › L0/L2.

Pointwise membership in fine coordinates via the same collect → rasterize →
precedence path as L0. The upsampled parent terrain is the background
fallback: cells outside the precise contour keep it unless the parent light
cell was region-painted, in which case the per-cell fallback is restored.
"""

from __future__ import annotations
from app.application.worldData.generators.terrain.landcover.types import (
    RegionSource,
    LandcoverCollectContext, LandcoverInputs,
)

import logging
from functools import cmp_to_key, partial

from app.application.jsonValidation import terrain, terrain_masks, terrain_system_keys
from app.application.worldData.generators.terrain.landcover.materializer import (
    LandcoverMaterializer,
)
from app.application.worldData.masks.regionPrecedence import (
    RegionCandidate,
    compare_region_candidates,
)
from app.application.worldData.masks.regionRasterContext import RegionRasterContext
from app.application.worldData.masks.regionRasterizer import (
    rasterize_claim_fine,
    rasterize_fine,
)
from app.application.worldData.masks.terrainMerge import (
    PRESERVE_HYDROLOGY_ROLES,
    may_paint_terrain,
    terrain_merge_rank,
)
from app.application.worldData.regions.coverageBackground import background_key_for_zone
from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.regionShape import Bounds
from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
from app.dataModel.topology.worldTopology import Coord

logger = logging.getLogger(__name__)

# L0 preserve roles lifted to the fine roles the hydro corridor emits.
_PRESERVE_FINE_ROLES = frozenset(
    role for role in (r.to_fine_role() for r in PRESERVE_HYDROLOGY_ROLES) if role is not None
)


def _hydro_preserved(coord: Coord, l0_hydro: dict[Coord, MapCellHydrology]) -> bool:
    entry = l0_hydro.get(coord)
    return entry is not None and entry.role in _PRESERVE_FINE_ROLES


def paint_regions_fine(
    ctx: LandcoverCollectContext,
    inputs: LandcoverInputs,
    parent_light: ParentLightTile,
    *,
    fine_terrain: dict[Coord, str],
    l0_hydro: dict[Coord, MapCellHydrology],
    tile_bbox: Bounds,
    climate: ClimateWorkingFields,
) -> dict[Coord, str]:
    """Paint region winners onto ``fine_terrain`` in place; return uid map."""
    world, scale = ctx.world, ctx.scale
    masks = terrain_masks(world)
    policy = masks.default_landcover
    if not masks.category_enabled(policy):
        return {}

    materializer = LandcoverMaterializer(inputs)
    materializer.begin_pass()
    regions = materializer.collect(ctx, policy)
    # Even with no surviving regions, restore parent-painted cells after a
    # removal/tombstone rather than carrying their stale terrain into L2.

    registry = terrain(world)
    merge_rank = partial(terrain_merge_rank, registry=registry)
    ranked = sorted(
        (
            RegionCandidate(
                r.current_type, r.spec, r.region_uid, r.claim_area,
                declared=r.source != RegionSource.AUTORESOLVE,
            )
            for r in regions
        ),
        key=cmp_to_key(
            lambda a, b: compare_region_candidates(a, b, merge_rank=merge_rank),
        ),
    )
    by_uid = {r.region_uid: r for r in regions}
    x_min, y_min, x_max, y_max = tile_bbox
    winners: dict[Coord, RegionCandidate] = {}
    for candidate in ranked:
        region = by_uid[candidate.region_uid]
        raster_ctx = RegionRasterContext(
            region.region_uid, region.spec, scale, region.topology,
        )
        if region.claim is not None:
            coords = rasterize_claim_fine(
                materializer.claim_index(region.claim, world, raster_ctx),
                world, raster_ctx, scope=tile_bbox,
            )
        else:
            coords = rasterize_fine(region.spec.shape, world, raster_ctx)
        for coord in coords:
            if x_min <= coord[0] <= x_max and y_min <= coord[1] <= y_max:
                winners.setdefault(coord, candidate)
    if not winners and not any(
        cell.region_uid for cell in parent_light.cells.values()
    ):
        return {}

    terrain_set = terrain_system_keys(world)
    background_cache: dict[tuple[int, int], str | None] = {}

    def background_key(cell: WorldMapCellWire | None) -> str | None:
        if cell is None:
            return None
        tx_ty = (int(cell.tx), int(cell.ty))
        if tx_ty not in background_cache:
            zone = ClimateZone.from_world_map_wire_id(cell.climate_zone_id) if cell.climate_zone_id is not None else None
            profile = climate.profile_for_key(RegistryKey[WorldClimateZoneRegistry](zone.system_climate)) if zone is not None else None
            background_cache[tx_ty] = background_key_for_zone(
                cell.climate_zone_id, masks, terrain_set, registry, profile=profile,
            )
        return background_cache[tx_ty]

    region_uid: dict[Coord, str] = {}
    painted = restored = preserved = blocked = 0
    for coord, current in fine_terrain.items():
        parent_cell = parent_light.cell_at(*parent_light.fine_to_tx_ty(*coord))
        region_painted_parent = parent_cell is not None and parent_cell.region_uid is not None
        winner = winners.get(coord)
        if winner is not None:
            if _hydro_preserved(coord, l0_hydro):
                preserved += 1
                continue
            if (
                region_painted_parent
                or current == background_key(parent_cell)
                or may_paint_terrain(current, winner.current_type, registry)
            ):
                fine_terrain[coord] = winner.current_type
                region_uid[coord] = winner.region_uid
                painted += 1
            else:
                blocked += 1
        elif region_painted_parent and not _hydro_preserved(coord, l0_hydro):
            fallback = background_key(parent_cell)
            if fallback is not None:
                fine_terrain[coord] = fallback
                restored += 1
    logger.debug(
        "landcover | fine_paint | tile_gx=%d tile_gy=%d regions=%d "
        "painted=%d restored=%d preserved=%d blocked=%d",
        parent_light.gx, parent_light.gy, len(regions), painted, restored,
        preserved, blocked,
    )
    return region_uid
