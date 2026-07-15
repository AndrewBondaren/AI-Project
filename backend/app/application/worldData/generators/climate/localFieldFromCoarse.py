"""Build ClimateAnchorField from coarse heightmap + locations (generators layer)."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.climateAssembler.passes.anchorCollectPass import (
    run_anchor_collect_pass,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _default_surface_terrain_key() -> str:
    """First canonical outdoor terrain — dataModel SoT (not a free literal)."""
    entry = WorldTerrainRegistry.canonical_defaults().root[0]
    return str(entry.system_terrain)


def cells_from_coarse_heightmap(world: World, coarse_hm: SurfaceHeightmap) -> list[MapCell]:
    """Synthetic macro surface cells for AnchorCollect (auto features + manual)."""
    terrain = _default_surface_terrain_key()
    return [
        MapCell(
            world_uid=world.world_uid,
            x=int(gx),
            y=int(gy),
            z=int(z),
            system_terrain=terrain,
        )
        for (gx, gy), z in coarse_hm.surface_z.items()
    ]


def build_local_field_from_coarse(
    world: World,
    locations: list[NamedLocation],
    pole_field: ClimatePoleField,
    coarse_hm: SurfaceHeightmap,
) -> ClimateAnchorField:
    cells = cells_from_coarse_heightmap(world, coarse_hm)
    return run_anchor_collect_pass(world, locations, cells, pole_field)
