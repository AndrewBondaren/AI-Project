"""Coarse Pass 1.4 — mountain Specs → raise ``surface_z`` on heightmap."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.terrain.mountains.collect import (
    collect_mountain_specs_for_coarse,
)
from app.application.worldData.generators.terrain.mountains.formPipeline import (
    coarse_disk_keys_for_spec,
)
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import (
    resolve_mountain_surface_z,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
from app.dataModel.terrainMasks.mountain.specs import MountainSpec

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
    """Raise ``surface_z`` from mountain Specs. Returns raised cell count."""
    del light_side  # Spec radius_m SoT; light_side unused after disk-radius removal
    masks = terrain_masks(world)
    policy = masks.default_mountains
    if not masks.category_enabled(policy):
        return 0

    z_min = world_z_min(world)
    z_max = world_z_max(world)
    cell_m = cell_size_m(world)
    keys = set(heightmap.surface_z.keys())
    specs = collect_mountain_specs_for_coarse(
        world,
        locations,
        masks,
        policy=policy,
        pole_field=pole_field,
        heightmap_keys=keys,
        cell_m=cell_m,
    )
    raised: set[tuple[int, int]] = set()
    for spec in specs:
        if not isinstance(spec, MountainSpec):
            continue
        for key in coarse_disk_keys_for_spec(spec, cell_m=cell_m):
            if key not in heightmap.surface_z or key in raised:
                continue
            base = heightmap.surface_z[key]
            heightmap.surface_z[key] = resolve_mountain_surface_z(
                base,
                z_min=z_min,
                z_max=z_max,
                kind=spec.kind,
                side_fraction=1.0,
            )
            raised.add(key)

    logger.debug(
        "relief_objects_mountain_z | world=%s raised=%d specs=%d",
        world.world_uid,
        len(raised),
        len(specs),
    )
    return len(raised)
