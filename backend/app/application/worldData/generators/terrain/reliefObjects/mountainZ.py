"""Coarse Pass 1.4 — mountain Specs → raise ``surface_z`` on heightmap."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.terrain.mountains.collect import (
    collect_mountain_entries_for_coarse,
)
from app.application.worldData.generators.terrain.mountains.formPipeline import (
    coarse_footprint_for_entry,
)
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import (
    resolve_mountain_surface_z,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
from app.dataModel.terrainMasks.mountain.enums import MountainKind
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.worldPack.worldMapCellsPerTile import (
    light_m_for,
    resolve_world_map_cells_per_tile,
)

if TYPE_CHECKING:
    from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
    from app.application.worldData.generators.terrain.types import SurfaceHeightmap
    from app.db.models.namedLocation import NamedLocation
    from app.db.models.world import World

logger = logging.getLogger(__name__)


def _entry_kind(spec: MountainSpec | MountainRangeSpec) -> MountainKind:
    return spec.kind


def apply_mountain_z(
    world: World,
    locations: list[NamedLocation],
    heightmap: SurfaceHeightmap,
    *,
    pole_field: ClimatePoleField,
    light_side: int,
) -> int:
    """Raise ``surface_z`` from mountain Specs (Q3-A FormRaster+SideFill). Returns raised cell count."""
    masks = terrain_masks(world)
    policy = masks.default_mountains
    if not masks.category_enabled(policy):
        return 0

    z_min = world_z_min(world)
    z_max = world_z_max(world)
    cell_m = cell_size_m(world)
    side = resolve_world_map_cells_per_tile(
        cell_m,
        getattr(world, "world_map_cells_per_tile", None),
    )
    if light_side is not None and int(light_side) > 0:
        side = max(1, int(light_side))
    light_m = float(light_m_for(cell_m, side))
    keys = set(heightmap.surface_z.keys())
    specs = collect_mountain_entries_for_coarse(
        world,
        locations,
        masks,
        policy=policy,
        pole_field=pole_field,
        heightmap_keys=keys,
        cell_m=cell_m,
    )
    # max fraction wins when Specs overlap
    frac_map: dict[tuple[int, int], float] = {}
    kind_map: dict[tuple[int, int], MountainKind] = {}
    for spec in specs:
        fp = coarse_footprint_for_entry(spec, cell_m=cell_m, light_m=light_m)
        kind = _entry_kind(spec)
        for key, frac in fp.items():
            if key not in keys:
                continue
            prev = frac_map.get(key)
            if prev is None or float(frac) > prev:
                frac_map[key] = float(frac)
                kind_map[key] = kind

    raised = 0
    for key, frac in frac_map.items():
        base = heightmap.surface_z[key]
        heightmap.surface_z[key] = resolve_mountain_surface_z(
            base,
            z_min=z_min,
            z_max=z_max,
            kind=kind_map[key],
            side_fraction=frac,
        )
        raised += 1

    logger.debug(
        "relief_objects_mountain_z | world=%s raised=%d specs=%d",
        world.world_uid,
        raised,
        len(specs),
    )
    return raised
