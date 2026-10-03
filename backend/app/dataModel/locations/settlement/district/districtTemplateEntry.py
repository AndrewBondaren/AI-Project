"""One `worlds.district_template_registry[]` row — SCH-DISTRICT-TEMPLATE."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import ECONOMIC_TIER
from app.dataModel.cascade.cascadeSpec import (
    CascadeChannel,
    ChannelKind,
)
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    ConnectionTypeKey,
)
from app.dataModel.registryKey import RegistryKey
from app.dataModel.roads.enums.streetLayout import StreetLayout
from app.dataModel.locations.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.locations.settlement.district.districtConnection import DistrictConnection
from app.dataModel.locations.settlement.district.placementCondition import PlacementCondition
from app.dataModel.locations.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.shared.ranges import EconomicTierRange, SizePct
from app.dataModel.locations.structure.building.plotLayoutTemplate import DrawingKey
from app.dataModel.locations.structure.enums.buildingPurpose import (
    DEFAULT_PURPOSE_MATCH,
    AllowedToken,
    BuildingPurposeMatch,
    coerce_allowed_list,
    coerce_purpose_match,
)

if TYPE_CHECKING:
    from app.dataModel.locations.settlement.district.worldDistrictTemplateRegistry import (
        WorldDistrictTemplateRegistry,
    )


class DistrictTemplateEntry(BaseModel):
    """tz_city_generation.md §9.2."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_name: StrictOnWire[RegistryKey[WorldDistrictTemplateRegistry]]
    display_name: StrictOnWire[str]
    district_type: StrictOnWire[str]
    district_subtype: DefaultOnWire[str | None] = None
    placement_conditions: DefaultOnWire[list[PlacementCondition]] = Field(default_factory=list)
    max_per_city: DefaultOnWire[int | None] = None
    size_pct: DefaultOnWire[SizePct | None] = None
    allowed_structure_types: DefaultOnWire[list[AllowedToken] | None] = None
    allowed_match: DefaultOnWire[BuildingPurposeMatch] = DEFAULT_PURPOSE_MATCH
    # District-level RANGE channel for `economic_tier`. Both district
    # edges (to district/settlement NL) are declared on the NL side —
    # NamedLocation already transitively imports this template, the
    # reverse would cycle (tz_cascade_context §2).
    economic_tier_range: Annotated[
        DefaultOnWire[EconomicTierRange | None],
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.DISTRICT, kind=ChannelKind.RANGE,
        ),
    ] = None
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
    deck: DefaultOnWire[int] = 0

    @field_validator("allowed_structure_types", mode="before")
    @classmethod
    def _coerce_allowed_purposes(cls, value: Any) -> Any:
        if value is None:
            return None
        return coerce_allowed_list(value)

    @field_validator("allowed_match", mode="before")
    @classmethod
    def _coerce_allowed_match(cls, value: Any) -> Any:
        if value is None:
            return DEFAULT_PURPOSE_MATCH
        return coerce_purpose_match(value)
