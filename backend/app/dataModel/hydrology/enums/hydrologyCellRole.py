"""Surface cell hydrology role — map_cells.hydrology.role (U19)."""

from __future__ import annotations

from enum import StrEnum


class HydrologyCellRole(StrEnum):
    COASTAL_SEA = "coastal_sea"
    OPEN_OCEAN  = "open_ocean"
    INLAND_SEA  = "inland_sea"
    LAKE        = "lake"
    RIVER_BED   = "river_bed"
    SHORE       = "shore"

    @classmethod
    def from_wire(cls, key: str | HydrologyCellRole | None) -> HydrologyCellRole | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None

    def is_open_water_role(self) -> bool:
        """Roles that imply liquid_candidate on surface-top after hydrology carve."""
        return self in {
            HydrologyCellRole.COASTAL_SEA,
            HydrologyCellRole.OPEN_OCEAN,
            HydrologyCellRole.INLAND_SEA,
            HydrologyCellRole.LAKE,
        }
