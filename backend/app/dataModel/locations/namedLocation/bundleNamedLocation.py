"""Bundle `locations[]` row — master wire before `NamedLocation` persist."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, IgnoreOnWire, StrictOnWire
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    CITY_SIZE,
    ECONOMIC_TIER,
    FLOOR_MATERIAL,
    SETTLEMENT_DENSITY,
    WALL_MATERIAL,
)
from app.dataModel.cascade.cascadeSpec import CascadeChannel, CascadeLink
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    ConnectionTypeKey,
)
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.locations.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.locations.settlement.district.districtTemplateEntry import (
    DistrictTemplateEntry,
)
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.locations.settlement.settlement.settlementSpecializationBind import (
    SettlementSpecializationBind,
)
from app.dataModel.locations.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
from app.dataModel.locations.settlement.settlement.worldLocationMoodRegistry import LocationMoodKey
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import SettlementSizeKey
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    DrawingKey,
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.room.roomDef import RoomDef


def _skeleton_default(name: str):
    return SettlementSkeleton.model_fields[name].default


class BundleNamedLocation(BaseModel):
    """tz_locations.md § named_locations — import wire contract."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    location_uid: StrictOnWire[str]
    display_name: StrictOnWire[str]
    system_location_type: StrictOnWire[str]

    parent_location_uid: DefaultOnWire[str | None] = None
    system_location_subtype: DefaultOnWire[str | None] = None
    system_description: IgnoreOnWire[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("system_description", "description"),
    )
    display_description: IgnoreOnWire[str | None] = None
    glossary_ref: DefaultOnWire[str | None] = None
    tag_refs: DefaultOnWire[list[str] | None] = None
    is_discovered: DefaultOnWire[bool] = False
    is_accessible: DefaultOnWire[bool] = True
    entry_difficulty: DefaultOnWire[int | None] = None
    guard_level: DefaultOnWire[int | None] = None
    system_location_mood: DefaultOnWire[LocationMoodKey | None] = None
    display_location_mood: DefaultOnWire[str | None] = None
    owner_uid: DefaultOnWire[str | None] = None
    system_climate_zone: DefaultOnWire[str | None] = None
    state_uid: DefaultOnWire[str | None] = None
    # Settlement-scope `system_city_size` node — top of the chain
    # (authored NL beats the skeleton node; the `above` materialize is
    # unnecessary: nothing overrides the settlement NL at its own level).
    system_city_size: Annotated[
        DefaultOnWire[SettlementSizeKey | None],
        CascadeChannel(
            CITY_SIZE, ScopeLevel.SETTLEMENT,
            below=CascadeLink(
                SettlementSkeleton, "system_city_size", ScopeLevel.SETTLEMENT,
            ),
        ),
    ] = None
    # Cascade channels for `economic_tier` — the stamped/authored node at
    # four levels; each edge declared once, where imports allow
    # (tz_cascade_context §2). Neighbours on the other side of an edge
    # are materialized by the contract verifier.
    system_economic_tier: Annotated[
        DefaultOnWire[EconomyTierKey | None],
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.ROOM,
            above=CascadeLink(RoomDef, "economic_tier", ScopeLevel.ROOM),
            below=CascadeLink(None, "system_economic_tier", ScopeLevel.BUILDING),
        ),
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.BUILDING,
            below=CascadeLink(PlotLayoutTemplate, "economic_tier", ScopeLevel.AREA),
        ),
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.DISTRICT,
            above=CascadeLink(PlotLayoutTemplate, "economic_tier_range", ScopeLevel.AREA),
            below=CascadeLink(DistrictTemplateEntry, "economic_tier_range", ScopeLevel.DISTRICT),
        ),
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.SETTLEMENT,
            above=CascadeLink(DistrictTemplateEntry, "economic_tier_range", ScopeLevel.DISTRICT),
            below=CascadeLink(SettlementSkeleton, "economic_tier", ScopeLevel.SETTLEMENT),
        ),
    ] = _skeleton_default(
        "economic_tier",
    )
    typical_districts: DefaultOnWire[list[TypicalDistrictRef] | None] = None
    system_settlement_specializations: DefaultOnWire[
        list[SettlementSpecializationBind] | None
    ] = None
    is_public: DefaultOnWire[bool] = False
    is_forbidden: DefaultOnWire[bool] = False
    is_selectable: DefaultOnWire[bool] = True
    map_x: DefaultOnWire[int | None] = None
    map_y: DefaultOnWire[int | None] = None
    map_z: DefaultOnWire[int | None] = None
    is_mobile: DefaultOnWire[bool] = False
    system_template_uid: DefaultOnWire[str | None] = None
    # `wall_material` chain — stamped/authored NL node at every scope
    # (room is the top, settlement the bottom); each self-edge is
    # declared once on the deeper side, the `above` direction is
    # materialized by the verifier (cascade-migration M9).
    parent_wall_material: Annotated[
        DefaultOnWire[MaterialKey | None],
        CascadeChannel(
            WALL_MATERIAL, ScopeLevel.ROOM,
            below=CascadeLink(
                None, "parent_wall_material", ScopeLevel.BUILDING,
            ),
        ),
        CascadeChannel(
            WALL_MATERIAL, ScopeLevel.BUILDING,
            below=CascadeLink(
                None, "parent_wall_material", ScopeLevel.AREA,
            ),
        ),
        CascadeChannel(
            WALL_MATERIAL, ScopeLevel.AREA,
            below=CascadeLink(
                None, "parent_wall_material", ScopeLevel.DISTRICT,
            ),
        ),
        CascadeChannel(
            WALL_MATERIAL, ScopeLevel.DISTRICT,
            below=CascadeLink(
                None, "parent_wall_material", ScopeLevel.SETTLEMENT,
            ),
        ),
        CascadeChannel(WALL_MATERIAL, ScopeLevel.SETTLEMENT),
    ] = None
    # `floor_material` chain — same shape (M9).
    parent_floor_material: Annotated[
        DefaultOnWire[MaterialKey | None],
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.ROOM,
            below=CascadeLink(
                None, "parent_floor_material", ScopeLevel.BUILDING,
            ),
        ),
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.BUILDING,
            below=CascadeLink(
                None, "parent_floor_material", ScopeLevel.AREA,
            ),
        ),
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.AREA,
            below=CascadeLink(
                None, "parent_floor_material", ScopeLevel.DISTRICT,
            ),
        ),
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.DISTRICT,
            below=CascadeLink(
                None, "parent_floor_material", ScopeLevel.SETTLEMENT,
            ),
        ),
        CascadeChannel(FLOOR_MATERIAL, ScopeLevel.SETTLEMENT),
    ] = None
    is_outdoor: DefaultOnWire[bool | None] = None
    is_sheltered: DefaultOnWire[bool] = False
    is_transit: DefaultOnWire[bool] = False
    created_at: DefaultOnWire[str | None] = None

    architectural_style: DefaultOnWire[str | None] = _skeleton_default("architectural_style")
    dominant_material: DefaultOnWire[MaterialKey | None] = _skeleton_default(
        "dominant_material",
    )
    # Settlement-scope `settlement_density` node — the district
    # template sits above (district-first), the skeleton node below.
    settlement_density: Annotated[
        DefaultOnWire[DistrictDensity | None],
        CascadeChannel(
            SETTLEMENT_DENSITY, ScopeLevel.SETTLEMENT,
            above=CascadeLink(
                DistrictTemplateEntry, "density", ScopeLevel.DISTRICT,
            ),
            below=CascadeLink(
                SettlementSkeleton, "settlement_density",
                ScopeLevel.SETTLEMENT,
            ),
        ),
    ] = _skeleton_default(
        "settlement_density",
    )
    frontage_type_order: DefaultOnWire[list[ConnectionTypeKey] | None] = (
        _skeleton_default("frontage_type_order")
    )
    plot_counts: DefaultOnWire[dict[DrawingKey, int] | None] = Field(
        default=_skeleton_default("plot_counts"),
        validation_alias=AliasChoices("plot_counts", "structure_counts"),
    )
    plot_priority: DefaultOnWire[dict[DrawingKey, int] | None] = Field(
        default=_skeleton_default("plot_priority"),
        validation_alias=AliasChoices("plot_priority", "structure_priority"),
    )
    perimeter_barrier: DefaultOnWire[PerimeterBarrier | None] = _skeleton_default(
        "perimeter_barrier",
    )

    def to_db_fields(self) -> dict[str, Any]:
        """Wire → ``NamedLocation`` kwargs."""
        return self.model_dump(exclude_none=True)
