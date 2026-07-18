"""Mountain contributor — declare + autoresolve (tz_map_light_bake)."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.terrain.reliefObjects import resolve_mountain_surface_z
from app.application.worldData.generators.terrain.reliefObjects.footprint import (
    declare_disk_keys,
    mountain_autoresolve_hit,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
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
from app.dataModel.masks.enums.maskDomainId import LightContributorId
from app.db.models.namedLocation import NamedLocation

logger = logging.getLogger(__name__)


class MountainContributor:
    name = LightContributorId.MOUNTAIN.value

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
        z_min = world_z_min(ctx.world)
        z_max = world_z_max(ctx.world)
        painted = 0
        raised: set[tuple[int, int, int, int]] = set()

        def _raise_z(gx: int, gy: int, tx: int, ty: int) -> None:
            key4 = (gx, gy, tx, ty)
            if key4 in raised:
                return
            cell = compose.get(gx, gy, tx, ty)
            if cell is None:
                return
            cell.surface_z = resolve_mountain_surface_z(
                cell.surface_z,
                z_min=z_min,
                z_max=z_max,
                policy=policy,
            )
            raised.add(key4)

        def _xy_of(loc: NamedLocation) -> tuple[int, int]:
            return meters_to_light(int(loc.map_x), int(loc.map_y), scale)

        declare_cells = declare_disk_keys(
            ctx.locations,
            radius=int(policy.declare_radius_light),
            xy_of=_xy_of,
        )
        if declare_cells:
            painted += paint_system_terrain(
                compose, declare_cells, key, masks=masks, tile_set=tile_set, preserve_hydro=True,
            )
            for lx, ly in declare_cells:
                gx = lx // scale.side
                gy = ly // scale.side
                tx = lx % scale.side
                ty = ly % scale.side
                if (gx, gy) not in tile_set:
                    continue
                cell = compose.get(gx, gy, tx, ty)
                if cell is not None and cell.system_terrain == key:
                    _raise_z(gx, gy, tx, ty)

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
                if not mountain_autoresolve_hit(
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
                    _raise_z(gx, gy, tx, ty)

        logger.debug(
            "light_contributor_mountain | world=%s painted=%d declare_cells=%d",
            ctx.world.world_uid,
            painted,
            len(declare_cells),
        )
