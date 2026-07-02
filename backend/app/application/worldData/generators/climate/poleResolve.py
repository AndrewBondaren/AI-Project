from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.masterData import climate_scalars
from app.application.worldData.generators.climate.climatePole import (
    ClimatePolePoint,
    PoleKind,
    PoleSource,
    derived_pole_temperature,
)
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.climate.locations import static_climate_poles
from app.application.worldData.generators.climate.math import world_seed
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import pole_specs_for_preset
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.application.worldData.generators.coordinates import (
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def peak_bounds(world: World) -> tuple[int, int]:
    return WorldClimateScalars.resolve_peak_bounds(
        world.climate_temperature_peak_min,
        world.climate_temperature_peak_max,
    )


def infer_pole_kind(location: NamedLocation) -> str:
    subtype = (location.system_location_subtype or "").lower()
    kind = PoleKind.from_wire(subtype)
    if kind is not None:
        return kind.wire_value
    return PoleKind.infer_from_climate_zone(location.system_climate_zone).wire_value


def _should_autoresolve(world: World) -> bool:
    return ClimatePoleMode.from_wire(climate_scalars(world).climate_pole_mode) == ClimatePoleMode.AUTORESOLVE


def collect_manual_pole(
    world: World,
    locations: list[NamedLocation],
    cell_m: int,
) -> ClimatePolePoint | None:
    poles = static_climate_poles(locations)
    if not poles:
        return None
    if len(poles) > 1:
        warn_once(
            world.world_uid,
            "multiple_poles",
            "climate_pole | world=%s declared %d poles; using first only",
            len(poles),
        )
    loc = poles[0]
    if not loc.system_climate_zone:
        warn_once(
            world.world_uid,
            f"pole_no_zone:{loc.location_uid}",
            "climate_pole | world=%s pole=%s has no system_climate_zone; ignored",
            loc.location_uid,
        )
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


def autoresolve_poles(
    world: World,
    bbox: GridBBox,
) -> list[ClimatePolePoint]:
    peak_min, peak_max = peak_bounds(world)
    specs              = pole_specs_for_preset(world.climate_pole_preset)
    seed               = world_seed(world)
    cx                 = (bbox.x_min + bbox.x_max) // 2
    cy                 = (bbox.y_min + bbox.y_max) // 2
    points: list[ClimatePolePoint] = []

    if len(specs) == 1:
        spec = specs[0]
        points.append(ClimatePolePoint(
            gx=cx + (seed % 3) - 1,
            gy=cy + ((seed >> 4) % 3) - 1,
            pole_kind=spec.pole_kind,
            system_climate_zone=spec.system_climate_zone,
            base_temperature=derived_pole_temperature(spec.pole_kind, peak_min, peak_max),
            weight=1.0,
            location_uid=None,
            source=PoleSource.AUTORESOLVE,
        ))
        return points

    for idx, spec in enumerate(specs):
        if idx == 0:
            gx, gy = cx, bbox.y_min
        else:
            gx, gy = cx, bbox.y_max
        points.append(ClimatePolePoint(
            gx=gx,
            gy=gy,
            pole_kind=spec.pole_kind,
            system_climate_zone=spec.system_climate_zone,
            base_temperature=derived_pole_temperature(spec.pole_kind, peak_min, peak_max),
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

    if not _should_autoresolve(world):
        warn_once(
            world.world_uid,
            "manual_mode_no_pole",
            "climate_pole | world=%s mode=manual with no climate_pole; empty pole field",
        )
        return ClimatePoleField(poles=(), bbox=bbox)

    if bbox is None:
        return ClimatePoleField(
            poles=tuple(autoresolve_poles(world, GridBBox(0, 1, 0, 1))),
            bbox=bbox,
        )

    return ClimatePoleField(
        poles=tuple(autoresolve_poles(world, bbox)),
        bbox=bbox,
    )
