"""Build coarse / fine climate field wires for World Pack — WP-PERF-32 / WP-18."""

from __future__ import annotations

from collections.abc import Mapping

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climateGeneratorService import ClimateGeneratorService
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    grid_tile_origin_x,
    grid_tile_origin_y,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.climate.climatePackSample import (
    sample_pack_climate_at,
    sample_pack_climate_at_macro,
)
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire, ClimateSampleWire
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def build_climate_coarse_wire(
    world: World,
    pole_field: ClimatePoleField,
    bbox: GridBBox,
    *,
    local_field: ClimateAnchorField | None = None,
    coarse_surface_z: dict[tuple[int, int], int] | None = None,
    uid_map: dict[str, NamedLocation] | None = None,
    climate: ClimateGeneratorService | None = None,
) -> ClimateFieldWire:
    """Coarse: one sample per macro-grid cell over *bbox* (pole+local + coarse z)."""
    svc = climate or ClimateGeneratorService()
    anchors = local_field if local_field is not None else ClimateAnchorField(())
    tile_m = cell_size_m(world)
    z_map = coarse_surface_z or {}
    width = bbox.x_max - bbox.x_min + 1
    height = bbox.y_max - bbox.y_min + 1
    samples: list[ClimateSampleWire] = []
    for gy in range(bbox.y_min, bbox.y_max + 1):
        for gx in range(bbox.x_min, bbox.x_max + 1):
            samples.append(
                sample_pack_climate_at_macro(
                    world,
                    pole_field,
                    anchors,
                    gx,
                    gy,
                    tile_m=tile_m,
                    coarse_surface_z=z_map,
                    uid_map=uid_map,
                    climate=svc,
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
    local_field: ClimateAnchorField | None = None,
    cells_per_side: int | None = None,
    coarse_surface_z: dict[tuple[int, int], int] | None = None,
    meter_z_overrides: Mapping[tuple[int, int], int] | None = None,
    parent_light: ParentLightTile | None = None,
    l2_surface_z: Mapping[tuple[int, int], int] | None = None,
    uid_map: dict[str, NamedLocation] | None = None,
    climate: ClimateGeneratorService | None = None,
) -> ClimateFieldWire:
    """Fine: denser light-grid samples over one macro-tile (origin in meters)."""
    svc = climate or ClimateGeneratorService()
    anchors = local_field if local_field is not None else ClimateAnchorField(())
    tile_m = cell_size_m(world)
    side = cells_per_side or resolve_world_map_cells_per_tile(
        tile_m,
        world.world_map_cells_per_tile,
    )
    scale = LightGridScale.from_tile(tile_m, side)
    step = scale.light_m
    origin_x = int(grid_tile_origin_x(tile_gx, tile_m))
    origin_y = int(grid_tile_origin_y(tile_gy, tile_m))
    samples: list[ClimateSampleWire] = []
    for ty in range(side):
        for tx in range(side):
            xm = origin_x + tx * step
            ym = origin_y + ty * step
            samples.append(
                sample_pack_climate_at(
                    world,
                    pole_field,
                    anchors,
                    xm=xm,
                    ym=ym,
                    tile_m=tile_m,
                    coarse_surface_z=coarse_surface_z,
                    meter_z_overrides=meter_z_overrides,
                    parent_light=parent_light,
                    l2_surface_z=l2_surface_z,
                    light_m=step,
                    uid_map=uid_map,
                    climate=svc,
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
