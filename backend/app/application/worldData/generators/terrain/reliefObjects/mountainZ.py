"""Coarse Pass 1.4 — mountain declare disk + autoresolve → raise ``surface_z``."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
    tile_origin_x,
    tile_origin_y,
)
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import (
    resolve_mountain_surface_z,
)
from app.application.worldData.generators.terrain.reliefObjects.footprint import (
    declare_disk_keys,
    declare_radius_macro,
    mountain_autoresolve_hit,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min

if TYPE_CHECKING:
    from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
    from app.application.worldData.generators.terrain.types import SurfaceHeightmap
    from app.db.models.namedLocation import NamedLocation
    from app.db.models.world import World

logger = logging.getLogger(__name__)


def apply_mountain_z(
    world: World,
    locations: list[NamedLocation],
    heightmap: SurfaceHeightmap,
    *,
    pole_field: ClimatePoleField,
    light_side: int,
) -> int:
    """Raise ``surface_z`` on declare + autoresolve mountain cells. Returns raised count."""
    masks = terrain_masks(world)
    policy = masks.default_mountains
    if not masks.category_enabled(policy):
        return 0

    z_min = world_z_min(world)
    z_max = world_z_max(world)
    seed = world_seed(world)
    cell_m = cell_size_m(world)
    raised: set[tuple[int, int]] = set()

    radius_macro = declare_radius_macro(int(policy.declare_radius_light), light_side)

    def _xy_of(loc: NamedLocation) -> tuple[int, int]:
        return (
            int(meters_to_grid_x(int(loc.map_x), cell_m)),
            int(meters_to_grid_y(int(loc.map_y), cell_m)),
        )

    declare_keys = declare_disk_keys(
        locations,
        radius=radius_macro,
        xy_of=_xy_of,
        accept=lambda key: key in heightmap.surface_z,
    )
    for key in declare_keys:
        base = heightmap.surface_z[key]
        heightmap.surface_z[key] = resolve_mountain_surface_z(
            base, z_min=z_min, z_max=z_max, policy=policy,
        )
        raised.add(key)

    if not policy.autoresolve:
        logger.debug(
            "relief_objects_mountain_z | world=%s raised=%d autoresolve=off",
            world.world_uid,
            len(raised),
        )
        return len(raised)

    for (gx, gy), base in list(heightmap.surface_z.items()):
        if (gx, gy) in raised:
            continue
        xm = int(tile_origin_x(gx, cell_m)) + cell_m // 2
        ym = int(tile_origin_y(gy, cell_m)) + cell_m // 2
        typical = int(pole_field.sample(world, gx, gy).typical_elevation_z)
        if not mountain_autoresolve_hit(
            seed=seed,
            xm=int(xm),
            ym=int(ym),
            surface_z=base,
            typical_elevation_z=typical,
            policy=policy,
        ):
            continue
        heightmap.surface_z[(gx, gy)] = resolve_mountain_surface_z(
            base, z_min=z_min, z_max=z_max, policy=policy,
        )
        raised.add((gx, gy))

    logger.debug(
        "relief_objects_mountain_z | world=%s raised=%d",
        world.world_uid,
        len(raised),
    )
    return len(raised)
