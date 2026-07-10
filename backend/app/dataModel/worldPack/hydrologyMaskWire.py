"""L0 light-grid hydrology wire — compact role for world_map.zst."""

from __future__ import annotations

from enum import IntEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole


class L0HydrologyRole(IntEnum):
    """u4 enum on L0 world map cells."""

    NONE = 0
    SEA = 1
    RIVER = 2
    LAKE = 3
    SHORE = 4

    @classmethod
    def from_wire(cls, value: int | str | L0HydrologyRole | None) -> L0HydrologyRole:
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
            case L0HydrologyRole.SEA:
                return HydrologyCellRole.COASTAL_SEA
            case L0HydrologyRole.RIVER:
                return HydrologyCellRole.RIVER_BED
            case L0HydrologyRole.LAKE:
                return HydrologyCellRole.LAKE
            case L0HydrologyRole.SHORE:
                return HydrologyCellRole.SHORE
            case _:
                return None


class HydrologyMaskWire(BaseModel):
    """L0 hydrology fields on a light cell."""

    SCHEMA_ID: ClassVar[str] = "SCH-HYDROLOGY-MASK-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    role: L0HydrologyRole = L0HydrologyRole.NONE
    width: int | None = None

    @field_validator("width", mode="before")
    @classmethod
    def _clamp_width(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return max(0, min(15, int(value)))
