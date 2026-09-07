"""One `worlds.district_template_registry[]` row — SCH-DISTRICT-TEMPLATE."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    ConnectionTypeKey,
)
from app.dataModel.roads.enums.streetLayout import StreetLayout
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.settlement.district.districtConnection import DistrictConnection
from app.dataModel.settlement.district.placementCondition import PlacementCondition
from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.shared.ranges import EconomicTierRange, SizePct
from app.dataModel.structure.building.buildingLayoutTemplate import DrawingKey


class DistrictTemplateEntry(BaseModel):
    """tz_city_generation.md §9.2."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_name: StrictOnWire[str]
    display_name: StrictOnWire[str]
    district_type: StrictOnWire[str]
    district_subtype: DefaultOnWire[str | None] = None
    placement_conditions: DefaultOnWire[list[PlacementCondition]] = Field(default_factory=list)
    max_per_city: DefaultOnWire[int | None] = None
    size_pct: DefaultOnWire[SizePct | None] = None
    allowed_structure_types: DefaultOnWire[list[str] | None] = None
    economic_tier_range: DefaultOnWire[EconomicTierRange | None] = None
    density: DefaultOnWire[DistrictDensity | None] = None
    street_layout: DefaultOnWire[StreetLayout] = StreetLayout.GRID
    connections: DefaultOnWire[list[DistrictConnection] | None] = None
    required_structures: DefaultOnWire[list[RequiredStructure] | None] = None
    frontage_type_order: DefaultOnWire[list[ConnectionTypeKey] | None] = None
    plot_counts: DefaultOnWire[dict[DrawingKey, int] | None] = Field(
        default=None,
        validation_alias=AliasChoices("plot_counts", "structure_counts"),
    )
    plot_priority: DefaultOnWire[dict[DrawingKey, int] | None] = Field(
        default=None,
        validation_alias=AliasChoices("plot_priority", "structure_priority"),
    )
    perimeter_barrier: DefaultOnWire[PerimeterBarrier | None] = None
