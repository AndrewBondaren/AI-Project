"""One `worlds.district_template_registry[]` row — SCH-DISTRICT-TEMPLATE."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy import OptionalOnWire, StrictOnWire
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
    placement_conditions: OptionalOnWire[list[PlacementCondition]] = Field(default_factory=list)
    max_per_city: OptionalOnWire[int | None] = None
    size_pct: OptionalOnWire[SizePct | None] = None
    allowed_structure_types: OptionalOnWire[list[str] | None] = None
    economic_tier_range: OptionalOnWire[EconomicTierRange | None] = None
    density: OptionalOnWire[str | None] = None
    street_layout: OptionalOnWire[str | None] = None
    connections: OptionalOnWire[list[DistrictConnection] | None] = None
    required_structures: OptionalOnWire[list[RequiredStructure] | None] = None
