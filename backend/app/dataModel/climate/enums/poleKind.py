"""Wire ``pole_kind`` keys and climate-zone grouping — tz_climate.md § Pole."""

from __future__ import annotations

from enum import Enum

CLIMATE_POLE_LOCATION_TYPE = "climate_pole"

# Must match ``ClimateZone`` wire keys — tz_climate.md pole inference.
_COLD_CLIMATE_ZONES = frozenset({"arctic", "subpolar", "tundra", "cold"})
_HOT_CLIMATE_ZONES = frozenset({"tropical", "desert", "subtropical", "volcanic"})


class PoleKind(Enum):
    COLD = "cold"
    HOT = "hot"
    NEUTRAL = "neutral"

    @property
    def wire_value(self) -> str:
        return self.value

    def __str__(self) -> str:
        return self.wire_value

    @classmethod
    def from_wire(cls, key: str | None) -> PoleKind | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.wire_value == norm:
                return member
        return None

    @classmethod
    def cold_climate_zones(cls) -> frozenset[str]:
        return _COLD_CLIMATE_ZONES

    @classmethod
    def hot_climate_zones(cls) -> frozenset[str]:
        return _HOT_CLIMATE_ZONES

    @classmethod
    def infer_from_climate_zone(cls, system_climate_zone: str | None) -> PoleKind:
        zone = (system_climate_zone or "").lower()
        if zone in cls.cold_climate_zones():
            return cls.COLD
        if zone in cls.hot_climate_zones():
            return cls.HOT
        return cls.NEUTRAL
