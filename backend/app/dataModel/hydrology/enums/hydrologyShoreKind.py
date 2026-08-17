"""Which water body a ``role=shore`` cell belongs to — paint class (U15)."""

from __future__ import annotations

from enum import StrEnum

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain


class HydrologyShoreKind(StrEnum):
    """Hydro category for shore paint — not ``system_terrain`` and not cell role."""

    RIVER = "river"
    MOUNTAIN_RIVER = "mountain_river"
    LAKE = "lake"
    SEA = "sea"

    @classmethod
    def from_wire(cls, key: str | HydrologyShoreKind | None) -> HydrologyShoreKind | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None

    @classmethod
    def for_open_water_role(cls, role: HydrologyCellRole | None) -> HydrologyShoreKind | None:
        """Open-water / basin role → shore paint kind. ``inland_sea`` is sea."""
        if role is HydrologyCellRole.LAKE:
            return cls.LAKE
        if role in {
            HydrologyCellRole.COASTAL_SEA,
            HydrologyCellRole.OPEN_OCEAN,
            HydrologyCellRole.INLAND_SEA,
        }:
            return cls.SEA
        return None

    def condition_terrain(self) -> ReliefConditionTerrain:
        """R34 shore class for this hydro category — not ``role`` as envelope key."""
        return {
            HydrologyShoreKind.RIVER: ReliefConditionTerrain.SHORE_RIVER,
            HydrologyShoreKind.MOUNTAIN_RIVER: ReliefConditionTerrain.SHORE_MOUNTAIN_RIVER,
            HydrologyShoreKind.LAKE: ReliefConditionTerrain.SHORE_LAKE,
            HydrologyShoreKind.SEA: ReliefConditionTerrain.SHORE_SEA,
        }[self]
