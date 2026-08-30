"""Authored outdoor city graph in pack — docs/tz_settlement_outdoor.md C2/C8/C15."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.dataModel.spatial.facing import Facing, coerce_facing_wire


class ShellCellWire(BaseModel):
    """Sparse outdoor cell on an area/building object — not FineTerrain column-runs."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    x: int
    y: int
    z: int
    system_terrain: str | None = None
    system_material: str | None = None
    system_building_element: str | None = None
    is_structural: bool = False
    location_uid: str | None = None
    system_facing: str | None = None


class BuildingShellWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: str
    shell_cells: list[ShellCellWire] = Field(default_factory=list)


class AreaSlotWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    cells: list[tuple[int, int]] = Field(default_factory=list)
    ground_z: int
    facing: Facing

    @field_validator("facing", mode="before")
    @classmethod
    def _parse_facing(cls, value: object) -> Facing:
        parsed = coerce_facing_wire(value)
        if parsed is None:
            raise ValueError("area slot facing required")
        return parsed


class AreaStructureWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    area_uid: str
    slot: AreaSlotWire
    barrier_cells: list[ShellCellWire] = Field(default_factory=list)
    yard_cells: list[ShellCellWire] = Field(default_factory=list)
    small_layouts: list[list[ShellCellWire]] = Field(default_factory=list)
    buildings: list[BuildingShellWire] = Field(default_factory=list)


class DistrictStructureWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: str
    barrier_cells: list[ShellCellWire] = Field(default_factory=list)
    areas: list[AreaStructureWire] = Field(default_factory=list)


class SettlementStructureWire(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-SETTLEMENT-STRUCTURE-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    settlement_uid: str
    barrier_cells: list[ShellCellWire] = Field(default_factory=list)
    districts: list[DistrictStructureWire] = Field(default_factory=list)
