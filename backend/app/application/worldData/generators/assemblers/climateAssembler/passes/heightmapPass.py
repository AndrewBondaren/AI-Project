import hashlib

from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _z_to_terrain(z: int, terrain_set: set[str]) -> str:
    if z >= 2:
        candidates = ["tundra", "plains"]
    elif z == 1:
        candidates = ["forest", "plains"]
    elif z == 0:
        candidates = ["plains"]
    else:
        candidates = ["liquid_body", "plains"]
    for t in candidates:
        if t in terrain_set:
            return t
    return next(iter(terrain_set), "plains")


def _cell_z_noise(world_seed: int, x: int, y: int, base_z: int, amplitude: int = 1) -> int:
    h = (world_seed ^ (x * 73856093) ^ (y * 19349663)) & 0xFFFFFFFF
    noise = (h % (2 * amplitude + 1)) - amplitude
    return base_z + noise


def _world_seed(world: World) -> int:
    return int(hashlib.md5(world.world_uid.encode()).hexdigest()[:8], 16)


def _static_anchors(locations: list[NamedLocation]) -> list[NamedLocation]:
    return [
        loc for loc in locations
        if loc.map_x is not None and loc.map_y is not None
        and loc.map_z is not None and not loc.is_mobile
    ]


def grid_bbox_from_locations(
    locations: list[NamedLocation],
    cell_m: int,
    padding: int,
) -> GridBBox | None:
    anchors = _static_anchors(locations)
    if not anchors:
        return None
    positions = [
        (meters_to_grid_x(l.map_x, cell_m), meters_to_grid_y(l.map_y, cell_m))
        for l in anchors
    ]
    return GridBBox(
        x_min=min(p[0] for p in positions) - padding,
        x_max=max(p[0] for p in positions) + padding,
        y_min=min(p[1] for p in positions) - padding,
        y_max=max(p[1] for p in positions) + padding,
    )


def run_heightmap_pass(
    world: World,
    locations: list[NamedLocation],
    pole_field: ClimatePoleField,
    climate: ClimateGeneratorService,
    padding: int = 2,
) -> list[MapCell]:
    """Pass 1: z + system_terrain only (no temperature/rainfall yet)."""
    bbox = grid_bbox_from_locations(locations, cell_size_m(world), padding)
    if bbox is None:
        return []

    terrain_set = {
        t["system_terrain"] for t in (world.terrain_registry or []) if "system_terrain" in t
    }
    z_min = world.z_min if world.z_min is not None else -3
    z_max = world.z_max if world.z_max is not None else 4
    seed  = _world_seed(world)

    cells: list[MapCell] = []
    for gy in range(bbox.y_min, bbox.y_max + 1):
        for gx in range(bbox.x_min, bbox.x_max + 1):
            sample = climate.sample_at_pole_field(world, pole_field, gx, gy)
            base_z = sample.typical_elevation_z
            z      = max(z_min, min(z_max, _cell_z_noise(seed, gx, gy, base_z)))
            cells.append(MapCell(
                world_uid=world.world_uid,
                x=gx,
                y=gy,
                z=z,
                system_terrain=_z_to_terrain(z, terrain_set),
            ))
    return cells
