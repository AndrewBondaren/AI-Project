"""One `worlds.district_template_registry[]` row — SCH-DISTRICT-TEMPLATE."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.settlement.district.districtConnection import DistrictConnection
from app.dataModel.settlement.district.placementCondition import PlacementCondition
from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.shared.ranges import EconomicTierRange, SizePct


class DistrictTemplateEntry(BaseModel):
    """tz_city_generation.md §9.2."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[str]
    display_name: StrictOnWire[str]
    district_type: StrictOnWire[str]
    placement_conditions: DefaultOnWire[list[PlacementCondition]] = Field(default_factory=list)
    max_per_city: DefaultOnWire[int | None] = None
    size_pct: DefaultOnWire[SizePct | None] = None
    allowed_structure_types: DefaultOnWire[list[str] | None] = None
    economic_tier_range: DefaultOnWire[EconomicTierRange | None] = None
    density: DefaultOnWire[str | None] = None
    street_layout: DefaultOnWire[str | None] = None
    connections: DefaultOnWire[list[DistrictConnection] | None] = None
    required_structures: DefaultOnWire[list[RequiredStructure] | None] = None
