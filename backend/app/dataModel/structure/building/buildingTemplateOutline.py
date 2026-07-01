"""SCH-BUILDING-TEMPLATE outline — standalone template JSON (global library)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.shared.ranges import EconomicTierRange, IntMinMax
from app.dataModel.structure.building.buildingTemplateRoomSlot import BuildingTemplateRoomSlot
from app.dataModel.structure.materialPick import MaterialPick


class BuildingTemplateOutline(BaseModel):
    """
    Outline for `building_templates.data` / inline world registry rows.
    Full generator schema — tz_building_generator.md §3 (levels[] deferred to JV-4).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[str]
    structure_type: StrictOnWire[str]
    display_name: StrictOnWire[str]
    glossary_ref: OptionalOnWire[str | None] = None
    description: OptionalOnWire[str | None] = None
    version: OptionalOnWire[str] = "1.0"
    levels: OptionalOnWire[IntMinMax | None] = None
    footprint: OptionalOnWire[dict[str, IntMinMax] | None] = None
    wall_material: OptionalOnWire[MaterialPick | None] = None
    floor_material: OptionalOnWire[MaterialPick | None] = None
    default_is_public: OptionalOnWire[bool] = False
    default_is_forbidden: OptionalOnWire[bool] = False
    rooms: OptionalOnWire[list[BuildingTemplateRoomSlot]] = Field(default_factory=list)
    perimeter_barrier: OptionalOnWire[PerimeterBarrier] = Field(default_factory=PerimeterBarrier)
    economic_tier_range: OptionalOnWire[EconomicTierRange | None] = None
