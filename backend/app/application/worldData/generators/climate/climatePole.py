from dataclasses import dataclass
from enum import StrEnum

CLIMATE_POLE_TYPE = "climate_pole"

DEFAULT_PEAK_MIN = -40
DEFAULT_PEAK_MAX = 45
POLE_BLEND_EPS   = 1.0
POLE_BLEND_POWER = 1.5


class PoleKind(StrEnum):
    COLD    = "cold"
    HOT     = "hot"
    NEUTRAL = "neutral"


class PoleSource(StrEnum):
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
