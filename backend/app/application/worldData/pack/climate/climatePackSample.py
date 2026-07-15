"""Shared pack climate sample — pole+local zone + z ladder + weather_at_elevation.

See ``.cursor/plans/pack-climate-correct-resolve.md`` and ``docs/tz_climate.md``.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climateGeneratorService import (
    ClimateGeneratorService,
    SurfaceClimateSample,
)
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.coordinates import (
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.application.worldData.generators.coordinates.worldTile import (
    tile_origin_x,
    tile_origin_y,
)
from app.dataModel.worldPack.climateFieldWire import ClimateSampleWire
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def resolve_pack_zone_sample(
    world: World,
    pole_field: ClimatePoleField,
    local_field: ClimateAnchorField,
    mgx: int,
    mgy: int,
    *,
    uid_map: dict[str, NamedLocation] | None = None,
    climate: ClimateGeneratorService | None = None,
) -> SurfaceClimateSample:
    """Pole + local tier — elevation does not choose zone."""
    svc = climate or ClimateGeneratorService()
    return svc.resolve_surface_sample(
        world, uid_map or {}, pole_field, local_field, mgx, mgy,
    )


def _l2_z_in_light_cell(
    xm: int,
    ym: int,
    l2_surface_z: Mapping[tuple[int, int], int],
    light_m: int,
) -> int | None:
    """Exact meter hit, else max surface_z in light-cell window [xm, xm+light_m)."""
    exact = l2_surface_z.get((int(xm), int(ym)))
    if exact is not None:
        return int(exact)
    if light_m <= 0:
        return None
    x0, y0 = int(xm), int(ym)
    x1, y1 = x0 + light_m, y0 + light_m
    best: int | None = None
    for (x, y), z in l2_surface_z.items():
        if x0 <= int(x) < x1 and y0 <= int(y) < y1:
            zi = int(z)
            if best is None or zi > best:
                best = zi
    return best


def resolve_pack_surface_z(
    *,
    xm: int,
    ym: int,
    tile_m: int,
    typical_elevation_z: int,
    coarse_surface_z: Mapping[tuple[int, int], int] | None = None,
    meter_z_overrides: Mapping[tuple[int, int], int] | None = None,
    parent_light: ParentLightTile | None = None,
    l2_surface_z: Mapping[tuple[int, int], int] | None = None,
    light_m: int | None = None,
) -> int:
    """Best-available surface z: L2 (light-cell window) → parent light → meter override → coarse → typical."""
    step = light_m
    if step is None and parent_light is not None:
        step = parent_light.light_m
    if l2_surface_z is not None and step is not None:
        hit = _l2_z_in_light_cell(xm, ym, l2_surface_z, int(step))
        if hit is not None:
            return hit
    elif l2_surface_z is not None:
        exact = l2_surface_z.get((int(xm), int(ym)))
        if exact is not None:
            return int(exact)
    if parent_light is not None:
        tx, ty = parent_light.meters_to_tx_ty(xm, ym)
        cell = parent_light.cell_at(tx, ty)
        if cell is not None:
            return int(cell.surface_z)
    if meter_z_overrides:
        hit = meter_z_overrides.get((int(xm), int(ym)))
        if hit is not None:
            return int(hit)
    mgx = int(meters_to_grid_x(xm, tile_m))
    mgy = int(meters_to_grid_y(ym, tile_m))
    if coarse_surface_z:
        hit = coarse_surface_z.get((mgx, mgy))
        if hit is not None:
            return int(hit)
    return int(typical_elevation_z)


def sample_pack_climate_at(
    world: World,
    pole_field: ClimatePoleField,
    local_field: ClimateAnchorField,
    *,
    xm: int,
    ym: int,
    tile_m: int,
    coarse_surface_z: Mapping[tuple[int, int], int] | None = None,
    meter_z_overrides: Mapping[tuple[int, int], int] | None = None,
    parent_light: ParentLightTile | None = None,
    l2_surface_z: Mapping[tuple[int, int], int] | None = None,
    light_m: int | None = None,
    uid_map: dict[str, NamedLocation] | None = None,
    climate: ClimateGeneratorService | None = None,
) -> ClimateSampleWire:
    """One pack climate sample at meters — zone from pole+local, temp/rain from z."""
    svc = climate or ClimateGeneratorService()
    mgx = int(meters_to_grid_x(xm, tile_m))
    mgy = int(meters_to_grid_y(ym, tile_m))
    zone = resolve_pack_zone_sample(
        world, pole_field, local_field, mgx, mgy, uid_map=uid_map, climate=svc,
    )
    z = resolve_pack_surface_z(
        xm=xm,
        ym=ym,
        tile_m=tile_m,
        typical_elevation_z=zone.typical_elevation_z,
        coarse_surface_z=coarse_surface_z,
        meter_z_overrides=meter_z_overrides,
        parent_light=parent_light,
        l2_surface_z=l2_surface_z,
        light_m=light_m,
    )
    temp, rain = svc.weather_at_elevation(
        world,
        zone.system_climate_zone,
        z,
        base_temperature_override=zone.base_temperature_override,
    )
    return ClimateSampleWire(temperature_base=temp, rainfall=rain)


def sample_pack_climate_at_macro(
    world: World,
    pole_field: ClimatePoleField,
    local_field: ClimateAnchorField,
    mgx: int,
    mgy: int,
    *,
    tile_m: int,
    coarse_surface_z: Mapping[tuple[int, int], int] | None = None,
    uid_map: dict[str, NamedLocation] | None = None,
    climate: ClimateGeneratorService | None = None,
) -> ClimateSampleWire:
    """Coarse grid sample — z from coarse map / typical; zone pole+local."""
    xm = tile_origin_x(mgx, tile_m)
    ym = tile_origin_y(mgy, tile_m)
    return sample_pack_climate_at(
        world,
        pole_field,
        local_field,
        xm=xm,
        ym=ym,
        tile_m=tile_m,
        coarse_surface_z=coarse_surface_z,
        uid_map=uid_map,
        climate=climate,
    )
