"""Build coarse / fine climate field wires for World Pack — WP-PERF-32 / WP-18."""

from __future__ import annotations

from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    grid_tile_origin_x,
    grid_tile_origin_y,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire, ClimateSampleWire
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.db.models.world import World


def _sample_wire(
    world: World,
    pole_field: ClimatePoleField,
    climate: ClimateGeneratorService,
    gx: int,
    gy: int,
    *,
    surface_z: int | None = None,
) -> ClimateSampleWire:
    pole = pole_field.sample(world, gx, gy)
    z = surface_z if surface_z is not None else pole.typical_elevation_z
    temp, rain = climate.weather_at_elevation(
        world,
        pole.system_climate_zone,
        z,
        base_temperature_override=pole.base_temperature_override,
    )
    return ClimateSampleWire(temperature_base=temp, rainfall=rain)


def build_climate_coarse_wire(
    world: World,
    pole_field: ClimatePoleField,
    bbox: GridBBox,
    *,
    coarse_surface_z: dict[tuple[int, int], int] | None = None,
    climate: ClimateGeneratorService | None = None,
) -> ClimateFieldWire:
    """Coarse: one sample per macro-grid cell over *bbox*."""
    svc = climate or ClimateGeneratorService()
    z_map = coarse_surface_z or {}
    width = bbox.x_max - bbox.x_min + 1
    height = bbox.y_max - bbox.y_min + 1
    samples: list[ClimateSampleWire] = []
    for gy in range(bbox.y_min, bbox.y_max + 1):
        for gx in range(bbox.x_min, bbox.x_max + 1):
            samples.append(
                _sample_wire(
                    world,
                    pole_field,
                    svc,
                    gx,
                    gy,
                    surface_z=z_map.get((gx, gy)),
                ),
            )
    return ClimateFieldWire(
        climate_status="coarse",
        origin_x=bbox.x_min,
        origin_y=bbox.y_min,
        width=width,
        height=height,
        sample_step_m=1,
        samples=samples,
    )


def build_climate_tile_wire(
    world: World,
    pole_field: ClimatePoleField,
    tile_gx: int,
    tile_gy: int,
    *,
    cells_per_side: int | None = None,
    coarse_surface_z: dict[tuple[int, int], int] | None = None,
    climate: ClimateGeneratorService | None = None,
) -> ClimateFieldWire:
    """Fine: denser light-grid samples over one macro-tile (origin in meters)."""
    svc = climate or ClimateGeneratorService()
    tile_m = cell_size_m(world)
    side = cells_per_side or resolve_world_map_cells_per_tile(
        tile_m,
        world.world_map_cells_per_tile,
    )
    scale = LightGridScale.from_tile(tile_m, side)
    step = scale.light_m
    origin_x = int(grid_tile_origin_x(tile_gx, tile_m))
    origin_y = int(grid_tile_origin_y(tile_gy, tile_m))
    z_map = coarse_surface_z or {}
    samples: list[ClimateSampleWire] = []
    for ty in range(side):
        for tx in range(side):
            xm = origin_x + tx * step
            ym = origin_y + ty * step
            mgx = int(meters_to_grid_x(xm, tile_m))
            mgy = int(meters_to_grid_y(ym, tile_m))
            samples.append(
                _sample_wire(
                    world,
                    pole_field,
                    svc,
                    mgx,
                    mgy,
                    surface_z=z_map.get((mgx, mgy)),
                ),
            )
    return ClimateFieldWire(
        climate_status="fine",
        origin_x=origin_x,
        origin_y=origin_y,
        width=side,
        height=side,
        sample_step_m=step,
        samples=samples,
    )
