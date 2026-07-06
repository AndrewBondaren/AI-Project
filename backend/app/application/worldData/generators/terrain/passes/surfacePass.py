from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    meter_bbox_for_tile,
    world_meter_xy,
)
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
    """Pass 1 — macro tile heightmap for hydrology planning (Gx, Gy keys)."""
    return run_surface_pass_coarse(world, locations, pole_field)


def run_surface_pass_coarse(
    world: World,
    locations: list[NamedLocation],
    pole_field: ClimatePoleField,
) -> SurfaceHeightmap | None:
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
    seed = world_seed(world)

    surface_z: dict[tuple[int, int], int] = {}
    for gy in range(bbox.y_min, bbox.y_max + 1):
        for gx in range(bbox.x_min, bbox.x_max + 1):
            sample = pole_field.sample(world, gx, gy)
            base_z = sample.typical_elevation_z
            z = max(z_min, min(z_max, cell_z_noise(seed, gx, gy, base_z)))
            surface_z[(gx, gy)] = z

    return SurfaceHeightmap(world_uid=world.world_uid, bbox=bbox, surface_z=surface_z)


def build_fine_surface_tile(
    world: World,
    pole_field: ClimatePoleField,
    tile_gx: int,
    tile_gy: int,
    coarse_surface_z: dict[tuple[int, int], int],
) -> dict[tuple[int, int], int]:
    """
  Fine meter surface_z for one macro tile — map_cell_size_m × map_cell_size_m keys (xm, ym).
  Base elevation from post-hydro coarse tile + per-meter noise.
  """
    cell_m = cell_size_m(world)
    z_min = world_z_min(world)
    z_max = world_z_max(world)
    seed = world_seed(world)

    sample = pole_field.sample(world, tile_gx, tile_gy)
    coarse_z = coarse_surface_z.get(
        (tile_gx, tile_gy),
        sample.typical_elevation_z,
    )

    surface_z: dict[tuple[int, int], int] = {}
    for ly in range(cell_m):
        for lx in range(cell_m):
            xm, ym = world_meter_xy(tile_gx, tile_gy, lx, ly, cell_m)
            delta = cell_z_noise(seed, xm, ym, 0, amplitude=1)
            z = max(z_min, min(z_max, coarse_z + delta))
            surface_z[(xm, ym)] = z

    return surface_z


def fine_surface_heightmap_for_tile(
    world: World,
    pole_field: ClimatePoleField,
    tile_gx: int,
    tile_gy: int,
    coarse_surface_z: dict[tuple[int, int], int],
) -> SurfaceHeightmap:
    cell_m = cell_size_m(world)
    meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
    return SurfaceHeightmap(
        world_uid=world.world_uid,
        bbox=meter_bbox,
        surface_z=build_fine_surface_tile(
            world, pole_field, tile_gx, tile_gy, coarse_surface_z,
        ),
    )
