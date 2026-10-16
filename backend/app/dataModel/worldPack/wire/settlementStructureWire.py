"""Authored outdoor city graph in pack — docs/tz_settlement_outdoor.md C2/C8/C15."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.dataModel.spatial.facing import Facing, coerce_facing_wire
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import EndpointRef, TransitionSpace
from app.dataModel.locations.transitions.transitionOrigin import TransitionOrigin
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry


class BuildingInteriorTransitionsWire(BaseModel):
    """Explicit layout scope; endpoint/owner references remain in the shared Transition POJO.

    Full reference snapshot validation is performed by the application before packing.
    Absence of this block means legacy shell data, not an empty interior transition collection.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["building-interior-transitions-v1"]
    world_uid: EndpointRef
    level_uids: list[EndpointRef]
    transitions: list[Transition]

    @model_validator(mode="after")
    def _scope(self, info: ValidationInfo) -> BuildingInteriorTransitionsWire:
        registry = (info.context or {}).get("transition_type_registry")
        if registry is None:
            registry = WorldTransitionTypeRegistry.canonical_engine()
        levels = set(self.level_uids)
        if len(levels) != len(self.level_uids):
            raise ValueError("duplicate interior transition level UID")
        seen = set()
        for item in self.transitions:
            if item.transition_uid in seen:
                raise ValueError("duplicate interior transition UID")
            seen.add(item.transition_uid)
            if item.world_uid != self.world_uid:
                raise ValueError("interior transition belongs to another world")
            entry = registry.entry_for(item.system_transition_type)
            if entry is None or entry.directional or item.origin == TransitionOrigin.RUNTIME:
                raise ValueError("runtime/directional transitions require SQL storage")
            for endpoint in (item.source, item.destination):
                if (endpoint.space != TransitionSpace.LEVEL or endpoint.geometry is None
                        or endpoint.level_uid not in levels):
                    raise ValueError("interior transition endpoint must belong to the explicit building level scope")
        return self


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
    interior_transitions: BuildingInteriorTransitionsWire | None = None


class AreaSlotWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    cells: list[tuple[int, int]] = Field(default_factory=list)
    ground_z: int
    facing: Facing
    height: int = 0
    z_deep: int = 0
    deck: int = 0

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
