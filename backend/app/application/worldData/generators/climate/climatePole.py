from dataclasses import dataclass

from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND, ClimatePoleBlendDefaults
from app.dataModel.climate.climatePoleTemperature import (
    POLE_TEMPERATURE_INSET_FRACTION,
    derived_pole_temperature,
)
from app.dataModel.climate.enums.poleKind import CLIMATE_POLE_LOCATION_TYPE, PoleKind
from app.dataModel.climate.enums.poleSource import PoleSource

CLIMATE_POLE_TYPE = CLIMATE_POLE_LOCATION_TYPE
POLE_BLEND_EPS = CLIMATE_POLE_BLEND.eps
POLE_BLEND_POWER = CLIMATE_POLE_BLEND.power


@dataclass(frozen=True)
class ClimatePolePoint:
    gx:                  int
    gy:                  int
    pole_kind:           str
    system_climate_zone: str
    base_temperature:    int
    weight:              float
    location_uid:        str | None
    source:              PoleSource
