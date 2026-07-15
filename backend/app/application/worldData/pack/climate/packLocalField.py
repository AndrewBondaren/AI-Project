"""Build ClimateAnchorField for pack bake from coarse heightmap + locations."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.climateAssembler.passes.anchorCollectPass import (
    run_anchor_collect_pass,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def cells_from_coarse_heightmap(world: World, coarse_hm: SurfaceHeightmap) -> list[MapCell]:
    """Synthetic macro surface cells for AnchorCollect (auto features + manual)."""
    return [
        MapCell(
            world_uid=world.world_uid,
            x=int(gx),
            y=int(gy),
            z=int(z),
            system_terrain="plains",
        )
        for (gx, gy), z in coarse_hm.surface_z.items()
    ]


def build_pack_local_field(
    world: World,
    locations: list[NamedLocation],
    pole_field: ClimatePoleField,
    coarse_hm: SurfaceHeightmap,
) -> ClimateAnchorField:
    cells = cells_from_coarse_heightmap(world, coarse_hm)
    return run_anchor_collect_pass(world, locations, cells, pole_field)
