"""World map light-cell wire (`world_map.zst` per tile)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.spatial.facing import Facing, coerce_facing_wire
from app.dataModel.worldPack.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole


class WorldMapCellWire(BaseModel):
    """Single light-grid cell inside a macro-tile."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-MAP-CELL-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    tx: int
    ty: int
    surface_z: int = 0
    system_terrain: str | None = None
    dominant_terrain_id: int = 0
    hydrology_role: WorldMapHydrologyRole = WorldMapHydrologyRole.NONE
    hydrology_width: int | None = None
    climate_zone_id: int | None = None
    location_pin: int | None = None
    system_facing: Facing | None = None
    """Uphill relief grade (tz_terrain_relief R3/R36s); stairs analogy."""
    system_grade_uid: str | None = None
    """Relief Grade instance uid (R36j); omit if cell not in a grade."""

    @field_validator("hydrology_role", mode="before")
    @classmethod
    def _parse_role(cls, value: object) -> WorldMapHydrologyRole:
        return WorldMapHydrologyRole.from_wire(value)  # type: ignore[arg-type]

    @field_validator("system_facing", mode="before")
    @classmethod
    def _parse_facing(cls, value: object) -> Facing | None:
        return coerce_facing_wire(value)

    @property
    def hydrology(self) -> HydrologyMaskWire:
        return HydrologyMaskWire(role=self.hydrology_role, width=self.hydrology_width)
