from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass
from app.application.worldData.generators.terrain.terrainZ import surface_terrain_at_z
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def run_heightmap_pass(
    world: World,
    locations: list[NamedLocation],
    pole_field: ClimatePoleField,
    padding: int = 2,
) -> list[MapCell]:
    """Climate compat: one surface cell per column from terrain Pass 1."""
    heightmap = run_surface_pass(world, locations, pole_field, padding)
    if heightmap is None:
        return []

    terrain_set = {
        t["system_terrain"] for t in (world.terrain_registry or []) if "system_terrain" in t
    }
    cells: list[MapCell] = []
    for (gx, gy), z in heightmap.surface_z.items():
        cells.append(MapCell(
            world_uid=world.world_uid,
            x=gx,
            y=gy,
            z=z,
            system_terrain=surface_terrain_at_z(z, terrain_set),
        ))
    return cells


def grid_bbox_from_locations(world, locations, padding):
    """Re-export for legacy scripts importing from heightmapPass."""
    from app.application.worldData.generators.terrain.passes.bbox import (
        grid_bbox_from_locations as _grid_bbox,
    )
    return _grid_bbox(world, locations, padding)
