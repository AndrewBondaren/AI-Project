from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.terrain.noise import cell_z_noise
from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def run_surface_pass(
    world: World,
    locations: list[NamedLocation],
    pole_field: ClimatePoleField,
) -> SurfaceHeightmap | None:
    """Pass 1: surface_z grid only (no MapCell subsurface)."""
    bbox = grid_bbox_from_locations(world, locations)
    if bbox is None:
        warn_once(
            world.world_uid,
            "heightmap_empty_bbox",
            "terrain pass | world=%s surface: no static anchors / bounds; returning empty grid",
        )
        return None

    z_min = world_z_min(world)
    z_max = world_z_max(world)
    seed  = world_seed(world)

    surface_z: dict[tuple[int, int], int] = {}
    for gy in range(bbox.y_min, bbox.y_max + 1):
        for gx in range(bbox.x_min, bbox.x_max + 1):
            sample = pole_field.sample(world, gx, gy)
            base_z = sample.typical_elevation_z
            z      = max(z_min, min(z_max, cell_z_noise(seed, gx, gy, base_z)))
            surface_z[(gx, gy)] = z

    return SurfaceHeightmap(world_uid=world.world_uid, bbox=bbox, surface_z=surface_z)
