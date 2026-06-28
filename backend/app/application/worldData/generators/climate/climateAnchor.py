from dataclasses import dataclass
from enum import StrEnum

CLIMATE_ANCHOR_TYPE = "climate_anchor"
ADMIN_ZONE_TYPES = frozenset({"region", "kingdom", "empire", "duchy"})
MANUAL_EXCLUSION_GRID = 2


class AnchorSource(StrEnum):
    MANUAL = "manual"
    AUTO   = "auto"
    ADMIN  = "admin"


@dataclass(frozen=True)
class ClimateAnchorPoint:
    """Single Voronoi center — one grid cell, not a footprint."""

    gx:                  int
    gy:                  int
    system_climate_zone: str
    location_uid:        str | None
    source:              AnchorSource
