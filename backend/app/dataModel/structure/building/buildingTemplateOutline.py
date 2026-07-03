"""SCH-BUILDING-TEMPLATE outline — standalone template JSON (global library)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
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
