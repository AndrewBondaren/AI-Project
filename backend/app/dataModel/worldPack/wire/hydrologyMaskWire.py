"""World map light-grid hydrology wire — compact role for world_map.zst."""

from __future__ import annotations

from enum import IntEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole


class WorldMapHydrologyRole(IntEnum):
    """u4 enum on world map light cells."""

    NONE = 0
    SEA = 1
    RIVER = 2
    LAKE = 3
    SHORE = 4

    @classmethod
    def from_wire(cls, value: int | str | WorldMapHydrologyRole | None) -> WorldMapHydrologyRole:
        if value is None:
            return cls.NONE
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            norm = value.strip().lower()
            for member in cls:
                if member.name.lower() == norm or str(member.value) == norm:
                    return member
            return cls.NONE
        try:
            iv = int(value)
            return cls(iv) if iv in cls._value2member_map_ else cls.NONE
        except (TypeError, ValueError):
            return cls.NONE

    def to_fine_role(self) -> HydrologyCellRole | None:
        match self:
            case WorldMapHydrologyRole.SEA:
                return HydrologyCellRole.COASTAL_SEA
            case WorldMapHydrologyRole.RIVER:
                return HydrologyCellRole.RIVER_BED
            case WorldMapHydrologyRole.LAKE:
                return HydrologyCellRole.LAKE
            case WorldMapHydrologyRole.SHORE:
                return HydrologyCellRole.SHORE
            case _:
                return None

    def merge_rank(self) -> int:
        """SEA ≥ LAKE ≥ RIVER ≥ SHORE ≥ NONE (tz_map_light_bake)."""
        match self:
            case WorldMapHydrologyRole.SEA:
                return 4
            case WorldMapHydrologyRole.LAKE:
                return 3
            case WorldMapHydrologyRole.RIVER:
                return 2
            case WorldMapHydrologyRole.SHORE:
                return 1
            case _:
                return 0

    @classmethod
    def merge(cls, a: WorldMapHydrologyRole, b: WorldMapHydrologyRole) -> WorldMapHydrologyRole:
        """Keep the higher-priority role when two writers hit the same light cell."""
        return a if a.merge_rank() >= b.merge_rank() else b


class HydrologyMaskWire(BaseModel):
    """World map hydrology fields on a light cell."""

    SCHEMA_ID: ClassVar[str] = "SCH-HYDROLOGY-MASK-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    role: WorldMapHydrologyRole = WorldMapHydrologyRole.NONE
    width: int | None = None

    @field_validator("width", mode="before")
    @classmethod
    def _clamp_width(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return max(0, min(15, int(value)))
