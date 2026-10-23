"""Climate-owned pure base pole layout shared by frozen and legacy callers."""

from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.climatePoleTemperature import derived_pole_temperature
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.enums.poleSource import PoleSource
from app.dataModel.climate.planning.climatePoints import ClimatePolePoint
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.climate.planning.inputs.climateBaseInput import ManualPoleInput


def autoresolve_base_poles(seed: int, preset: ClimatePolePreset, peak_min: int, peak_max: int,
                            bbox: GridBBox) -> tuple[ClimatePolePoint, ...]:
    specs = preset.pole_specs()
    cx, cy = (bbox.x_min + bbox.x_max) // 2, (bbox.y_min + bbox.y_max) // 2
    points: list[ClimatePolePoint] = []
    for index, spec in enumerate(specs):
        if len(specs) == 1:
            gx, gy = cx + (seed % 3) - 1, cy + ((seed >> 4) % 3) - 1
        else:
            gx, gy = cx, bbox.y_min if index == 0 else bbox.y_max
        kind = PoleKind.from_wire(spec.pole_kind)
        if kind is None:
            raise ValueError("preset contains an unknown pole kind")
        points.append(ClimatePolePoint(gx=GridX(gx), gy=GridY(gy), pole_kind=kind,
            system_climate_zone=RegistryKey[WorldClimateZoneRegistry](spec.system_climate_zone),
            base_temperature=derived_pole_temperature(kind, peak_min, peak_max),
            weight=1.0, location_uid=None, source=PoleSource.AUTORESOLVE))
    return tuple(points)


def manual_base_pole(manual: ManualPoleInput, fine_span: int, peak_min: int, peak_max: int) -> ClimatePolePoint | None:
    if manual.zone is None:
        return None
    return ClimatePolePoint(gx=GridX(manual.position[0] // fine_span),
        gy=GridY(manual.position[1] // fine_span), pole_kind=manual.kind,
        system_climate_zone=manual.zone, base_temperature=derived_pole_temperature(manual.kind, peak_min, peak_max),
        weight=1.0, location_uid=manual.location_uid, source=PoleSource.MANUAL)


