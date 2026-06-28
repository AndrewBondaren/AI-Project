import hashlib

from app.application.worldData.generators.climate.climatePole import (
    CLIMATE_POLE_TYPE,
    DEFAULT_PEAK_MAX,
    DEFAULT_PEAK_MIN,
    ClimatePolePoint,
    PoleKind,
    PoleSource,
)
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.climate.climateZone import ClimateZone
from app.application.worldData.generators.coordinates import (
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

_COLD_ZONES = (ClimateZone.ARCTIC, ClimateZone.SUBPOLAR, ClimateZone.TUNDRA, ClimateZone.COLD)
_HOT_ZONES  = (ClimateZone.TROPICAL, ClimateZone.DESERT, ClimateZone.SUBTROPICAL, ClimateZone.VOLCANIC)


def peak_bounds(world: World) -> tuple[int, int]:
    peak_min = world.climate_temperature_peak_min if world.climate_temperature_peak_min is not None else DEFAULT_PEAK_MIN
    peak_max = world.climate_temperature_peak_max if world.climate_temperature_peak_max is not None else DEFAULT_PEAK_MAX
    if peak_min > peak_max:
        peak_min, peak_max = peak_max, peak_min
    return peak_min, peak_max


def derived_pole_temperature(pole_kind: str, peak_min: int, peak_max: int) -> int:
    span = peak_max - peak_min
    if pole_kind == PoleKind.HOT:
        return round(peak_max - 0.2 * span)
    if pole_kind == PoleKind.COLD:
        return round(peak_min + 0.2 * span)
    return round((peak_min + peak_max) / 2)


def infer_pole_kind(location: NamedLocation) -> str:
    subtype = (location.system_location_subtype or "").lower()
    if subtype in {PoleKind.COLD, PoleKind.HOT, PoleKind.NEUTRAL}:
        return subtype
    zone = (location.system_climate_zone or "").lower()
    if zone in {z.value for z in _COLD_ZONES}:
        return PoleKind.COLD
    if zone in {z.value for z in _HOT_ZONES}:
        return PoleKind.HOT
    return PoleKind.NEUTRAL


def _static_poles(locations: list[NamedLocation]) -> list[NamedLocation]:
    return [
        loc for loc in locations
        if loc.system_location_type == CLIMATE_POLE_TYPE
        and loc.map_x is not None and loc.map_y is not None
        and loc.map_z is not None and not loc.is_mobile
    ]


def collect_manual_pole(
    world: World,
    locations: list[NamedLocation],
    cell_m: int,
) -> ClimatePolePoint | None:
    poles = _static_poles(locations)
    if not poles:
        return None
    loc = poles[0]
    if not loc.system_climate_zone:
        return None
    peak_min, peak_max = peak_bounds(world)
    kind = infer_pole_kind(loc)
    return ClimatePolePoint(
        gx=meters_to_grid_x(loc.map_x, cell_m),
        gy=meters_to_grid_y(loc.map_y, cell_m),
        pole_kind=kind,
        system_climate_zone=loc.system_climate_zone,
        base_temperature=derived_pole_temperature(kind, peak_min, peak_max),
        weight=1.0,
        location_uid=loc.location_uid,
        source=PoleSource.MANUAL,
    )


def _world_seed(world: World) -> int:
    return int(hashlib.md5(world.world_uid.encode()).hexdigest()[:8], 16)


def _preset_pole_specs(preset: str) -> list[tuple[str, str]]:
    key = (preset or "binary").lower()
    if key == "ice":
        return [(PoleKind.COLD, ClimateZone.ARCTIC)]
    if key == "desert":
        return [(PoleKind.HOT, ClimateZone.DESERT)]
    return [
        (PoleKind.COLD, ClimateZone.ARCTIC),
        (PoleKind.HOT, ClimateZone.TROPICAL),
    ]


def autoresolve_poles(
    world: World,
    bbox: GridBBox,
) -> list[ClimatePolePoint]:
    peak_min, peak_max = peak_bounds(world)
    specs              = _preset_pole_specs(world.climate_pole_preset)
    seed               = _world_seed(world)
    cx                 = (bbox.x_min + bbox.x_max) // 2
    cy                 = (bbox.y_min + bbox.y_max) // 2
    points: list[ClimatePolePoint] = []

    if len(specs) == 1:
        kind, zone = specs[0]
        points.append(ClimatePolePoint(
            gx=cx + (seed % 3) - 1,
            gy=cy + ((seed >> 4) % 3) - 1,
            pole_kind=kind,
            system_climate_zone=zone,
            base_temperature=derived_pole_temperature(kind, peak_min, peak_max),
            weight=1.0,
            location_uid=None,
            source=PoleSource.AUTORESOLVE,
        ))
        return points

    for idx, (kind, zone) in enumerate(specs):
        if idx == 0:
            gx, gy = cx, bbox.y_min
        else:
            gx, gy = cx, bbox.y_max
        points.append(ClimatePolePoint(
            gx=gx,
            gy=gy,
            pole_kind=kind,
            system_climate_zone=zone,
            base_temperature=derived_pole_temperature(kind, peak_min, peak_max),
            weight=1.0,
            location_uid=None,
            source=PoleSource.AUTORESOLVE,
        ))
    return points


def resolve_pole_field(
    world: World,
    locations: list[NamedLocation],
    cell_m: int,
    bbox: GridBBox | None,
) -> ClimatePoleField:
    manual = collect_manual_pole(world, locations, cell_m)
    if manual is not None:
        return ClimatePoleField(poles=(manual,), bbox=bbox)

    if bbox is None:
        return ClimatePoleField(poles=tuple(autoresolve_poles(world, GridBBox(0, 1, 0, 1))), bbox=bbox)

    return ClimatePoleField(
        poles=tuple(autoresolve_poles(world, bbox)),
        bbox=bbox,
    )
