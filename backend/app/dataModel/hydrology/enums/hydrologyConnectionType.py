"""Wire `connection_type` keys for hydrology declare — ENUM-E E-10, tz_terrain_hydrology.md."""

from __future__ import annotations

from enum import StrEnum


class HydrologyConnectionType(StrEnum):
    LAKE_SHORELINE = "lake_shoreline"
    COASTLINE = "coastline"
    RIVER = "river"
    MOUNTAIN_RIVER = "mountain_river"

    @classmethod
    def from_wire(cls, key: str | HydrologyConnectionType | None) -> HydrologyConnectionType | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None
