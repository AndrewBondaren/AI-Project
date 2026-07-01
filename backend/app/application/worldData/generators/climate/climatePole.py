from dataclasses import dataclass
from enum import StrEnum

from app.dataModel.climate.worldClimateScalars import WorldClimateScalars

CLIMATE_POLE_TYPE = "climate_pole"

_scalars = WorldClimateScalars.canonical_defaults()
DEFAULT_PEAK_MIN = _scalars.climate_temperature_peak_min if _scalars.climate_temperature_peak_min is not None else -40
DEFAULT_PEAK_MAX = _scalars.climate_temperature_peak_max if _scalars.climate_temperature_peak_max is not None else 45
POLE_BLEND_EPS   = 1.0
POLE_BLEND_POWER = 1.5


class PoleKind(StrEnum):
    COLD    = "cold"
    HOT     = "hot"
    NEUTRAL = "neutral"


class PoleSource(StrEnum):
    MANUAL      = "manual"
    AUTORESOLVE = "autoresolve"


class PoleMode(StrEnum):
    MANUAL      = "manual"
    AUTORESOLVE = "autoresolve"


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
