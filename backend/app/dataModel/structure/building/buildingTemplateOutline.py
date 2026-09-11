"""SCH-BUILDING-TEMPLATE outline — standalone template JSON (global library)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.shared.ranges import EconomicTierRange, IntMinMax
from app.dataModel.structure.building.buildingLayoutTemplate import DrawingKey
from app.dataModel.structure.building.buildingTemplateRoomSlot import BuildingTemplateRoomSlot
from app.dataModel.structure.enums.buildingPurpose import (
    BuildingPurpose,
    coerce_purpose_list,
    primary_purpose,
)
from app.dataModel.structure.materialPick import MaterialPick


class BuildingTemplateOutline(BaseModel):
    """
    Outline for `building_templates.data` / inline world registry rows.
    Full generate schema (`levels[]` as floors) — `BuildingLayoutTemplate` + **POJO-D-16** / JV-4b.
    Here `levels` is IntMinMax (library), `rooms` is `BuildingTemplateRoomSlot` — not generate rooms.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[DrawingKey]
    structure_types: DefaultOnWire[list[BuildingPurpose]] = Field(
        default_factory=lambda: coerce_purpose_list(None),
    )
    display_name: StrictOnWire[str]
    # Extract drawings only. ENUM-E: ore / stone / timber / liquid.
    resource_kind: DefaultOnWire[ResourceKind | None] = None
    # Farm drawings only. ENUM-E: grain / vegetable / fruit / fiber / fodder.
    crop_kind: DefaultOnWire[CropKind | None] = None
    # Livestock drawings only. ENUM-E: meat / dairy / fiber / draft / mount.
    livestock_kind: DefaultOnWire[LivestockKind | None] = None
    # Extract/farm/livestock N+1 tags when resource_kind, crop_kind or livestock_kind is set.
    subjects: DefaultOnWire[list[str]] = Field(default_factory=list)
    glossary_ref: DefaultOnWire[str | None] = None
    description: DefaultOnWire[str | None] = None
    version: DefaultOnWire[str] = "1.0"
    levels: DefaultOnWire[IntMinMax | None] = None
    footprint: DefaultOnWire[dict[str, IntMinMax] | None] = None
    wall_material: DefaultOnWire[MaterialPick | None] = None
    floor_material: DefaultOnWire[MaterialPick | None] = None
    default_is_public: DefaultOnWire[bool] = False
    default_is_forbidden: DefaultOnWire[bool] = False
    rooms: DefaultOnWire[list[BuildingTemplateRoomSlot]] = Field(default_factory=list)
    perimeter_barrier: DefaultOnWire[PerimeterBarrier] = Field(default_factory=PerimeterBarrier)
    economic_tier_range: DefaultOnWire[EconomicTierRange | None] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_structure_types(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        raw = payload.get("structure_types")
        if raw is None:
            raw = payload.get("structure_type")
        payload["structure_types"] = coerce_purpose_list(raw, empty_as_house=True)
        return payload

    @property
    def structure_type(self) -> str:
        return str(primary_purpose(self.structure_types))
