"""Mountain contributor — declare + autoresolve (tz_map_light_bake)."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.masks.mountainField import is_mountain_autoresolve
from app.application.worldData.pack.bake.lightGrid.paintTerrain import (
    paint_system_terrain,
    paint_system_terrain_cell,
)
from app.application.worldData.masks.resolveForestPlains import profile_for_zone_key
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import (
    light_cell_center_m,
    meters_to_light,
)
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.locations.enums.geographicSubtype import (
    GEOGRAPHIC_LOCATION_TYPE,
    GeographicSubtype,
)

logger = logging.getLogger(__name__)

_DECLARE_SUBTYPES = frozenset({GeographicSubtype.MOUNTAIN, GeographicSubtype.PEAK})


class MountainContributor:
    name = "mountain"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        masks = terrain_masks(ctx.world)
        policy = masks.default_mountains
        if not masks.category_enabled(policy):
            logger.debug(
                "light_contributor_mountain | world=%s skipped=disabled",
                ctx.world.world_uid,
            )
            return

        scale = compose.scale
        tile_set = set(ctx.tiles)
        seed = world_seed(ctx.world)
        key = policy.system_terrain
        painted = 0

        # Declare: geographic.mountain / peak disks.
        declare_cells: set[tuple[int, int]] = set()
        radius = int(policy.declare_radius_light)
        for loc in ctx.locations:
            if loc.system_location_type != GEOGRAPHIC_LOCATION_TYPE:
                continue
            subtype = GeographicSubtype.from_wire(getattr(loc, "system_location_subtype", None))
            if subtype not in _DECLARE_SUBTYPES:
                continue
            if loc.map_x is None or loc.map_y is None:
                continue
            lx, ly = meters_to_light(int(loc.map_x), int(loc.map_y), scale)
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy > radius * radius:
                        continue
                    declare_cells.add((lx + dx, ly + dy))
        if declare_cells:
            painted += paint_system_terrain(
                compose, declare_cells, key, masks=masks, tile_set=tile_set, preserve_hydro=True,
            )

        if not policy.autoresolve:
            logger.debug(
                "light_contributor_mountain | world=%s painted=%d autoresolve=off",
                ctx.world.world_uid,
                painted,
            )
            return

        for gx, gy in ctx.tiles:
            for tx, ty, cell in compose.iter_tile(gx, gy):
                zone = (
                    ClimateZone.from_world_map_wire_id(cell.climate_zone_id)
                    if cell.climate_zone_id is not None
                    else None
                )
                zone_key = zone.system_climate if zone is not None else None
                profile = profile_for_zone_key(zone_key)
                xm, ym = light_cell_center_m(gx, gy, tx, ty, scale)
                if not is_mountain_autoresolve(
                    seed=seed,
                    xm=int(xm),
                    ym=int(ym),
                    surface_z=cell.surface_z,
                    typical_elevation_z=profile.typical_elevation_z,
                    policy=policy,
                ):
                    continue
                if paint_system_terrain_cell(
                    compose, gx, gy, tx, ty, key, masks=masks, preserve_hydro=True,
                ):
                    painted += 1

        logger.debug(
            "light_contributor_mountain | world=%s painted=%d declare_cells=%d",
            ctx.world.world_uid,
            painted,
            len(declare_cells),
        )
