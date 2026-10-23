from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.jsonValidation import climate_scalars
from app.application.worldData.generators.climate.climatePole import (
    ClimatePolePoint,
)
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.application.worldData.generators.climate.locations import static_climate_poles
from app.application.worldData.generators.climate.math import world_seed
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.application.worldData.generators.climate.planning.climatePlanProvider import autoresolve_base_poles, manual_base_pole
from app.dataModel.climate.planning.inputs.climateBaseInput import ManualPoleInput
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def peak_bounds(world: World) -> tuple[int, int]:
    scalars = climate_scalars(world)
    return WorldClimateScalars.resolve_peak_bounds(
        scalars.climate_temperature_peak_min,
        scalars.climate_temperature_peak_max,
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
    return manual_base_pole(ManualPoleInput(location_uid=loc.location_uid,
        position=(FineX(loc.map_x), FineY(loc.map_y)),
        kind=PoleKind(kind), zone=RegistryKey[WorldClimateZoneRegistry](loc.system_climate_zone)), cell_m, peak_min, peak_max)


def autoresolve_poles(
    world: World,
    bbox: GridBBox,
) -> list[ClimatePolePoint]:
    peak_min, peak_max = peak_bounds(world)
    return list(autoresolve_base_poles(world_seed(world),
        ClimatePolePreset.from_wire(climate_scalars(world).climate_pole_preset), peak_min, peak_max, bbox))


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
