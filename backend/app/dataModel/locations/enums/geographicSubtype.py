"""Wire `system_location_subtype` when type is geographic — HY-GEO-1, tz_terrain_hydrology.md."""

from __future__ import annotations

from enum import StrEnum

GEOGRAPHIC_LOCATION_TYPE = "geographic"


class GeographicSubtype(StrEnum):
    MOUNTAIN = "mountain"
    PEAK = "peak"
    PLAIN = "plain"
    LAKE = "lake"
    SEA = "sea"
    OCEAN = "ocean"
    INLAND_SEA = "inland_sea"
    ISLAND = "island"
    COAST = "coast"
    RIVER = "river"

    @classmethod
    def from_wire(cls, key: str | GeographicSubtype | None) -> GeographicSubtype | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None
