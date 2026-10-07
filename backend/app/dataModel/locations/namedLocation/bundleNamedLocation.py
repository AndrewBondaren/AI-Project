"""Bundle `locations[]` row — master wire before `NamedLocation` persist."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, IgnoreOnWire, StrictOnWire
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    ECONOMIC_TIER,
    FLOOR_MATERIAL,
    WALL_MATERIAL,
)
from app.dataModel.cascade.cascadeSpec import CascadeChannel, CascadeLink, FieldRef
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    ConnectionTypeKey,
)
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.locations.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.locations.settlement.district.districtTemplateEntry import (
    DistrictTemplateEntry,
)
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.locations.settlement.settlement.settlementSpecializationBind import (
    SettlementSpecializationBind,
)
from app.dataModel.locations.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
from app.dataModel.locations.settlement.settlement.worldLocationMoodRegistry import LocationMoodKey
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    DrawingKey,
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.dataModel.locations.locationPayload import LocationPayload
from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload


def _skeleton_default(name: str):
    return SettlementSkeleton.model_fields[name].default


# Selectors live outside Annotated so static checkers inspect attributes.
_ROOM_DEF_ECONOMIC_TIER = FieldRef(lambda: RoomDef, lambda pojo: pojo.economic_tier)
_BUNDLE_NAMED_LOCATION_SYSTEM_ECONOMIC_TIER = FieldRef(lambda: BundleNamedLocation, lambda pojo: pojo.system_economic_tier)
_PLOT_LAYOUT_TEMPLATE_ECONOMIC_TIER = FieldRef(lambda: PlotLayoutTemplate, lambda pojo: pojo.economic_tier)
_PLOT_LAYOUT_TEMPLATE_ECONOMIC_TIER_RANGE = FieldRef(lambda: PlotLayoutTemplate, lambda pojo: pojo.economic_tier_range)
_DISTRICT_TEMPLATE_ENTRY_ECONOMIC_TIER_RANGE = FieldRef(lambda: DistrictTemplateEntry, lambda pojo: pojo.economic_tier_range)
_SETTLEMENT_SKELETON_ECONOMIC_TIER = FieldRef(lambda: SettlementSkeleton, lambda pojo: pojo.economic_tier)
_BUNDLE_NAMED_LOCATION_PARENT_WALL_MATERIAL = FieldRef(lambda: BundleNamedLocation, lambda pojo: pojo.parent_wall_material)
_BUNDLE_NAMED_LOCATION_PARENT_FLOOR_MATERIAL = FieldRef(lambda: BundleNamedLocation, lambda pojo: pojo.parent_floor_material)


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
    # Cascade channels for `economic_tier` — the stamped/authored node at
    # four levels; each edge declared once, where imports allow
    # (tz_cascade_context §2). Neighbours on the other side of an edge
    # are materialized by the contract verifier.
    system_economic_tier: Annotated[
        DefaultOnWire[EconomyTierKey | None],
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.ROOM,
            above=CascadeLink(_ROOM_DEF_ECONOMIC_TIER, ScopeLevel.ROOM),
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_SYSTEM_ECONOMIC_TIER, ScopeLevel.BUILDING),
        ),
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.BUILDING,
            below=CascadeLink(_PLOT_LAYOUT_TEMPLATE_ECONOMIC_TIER, ScopeLevel.AREA),
        ),
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.DISTRICT,
            above=CascadeLink(_PLOT_LAYOUT_TEMPLATE_ECONOMIC_TIER_RANGE, ScopeLevel.AREA),
            below=CascadeLink(_DISTRICT_TEMPLATE_ENTRY_ECONOMIC_TIER_RANGE, ScopeLevel.DISTRICT),
        ),
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.SETTLEMENT,
            above=CascadeLink(_DISTRICT_TEMPLATE_ENTRY_ECONOMIC_TIER_RANGE, ScopeLevel.DISTRICT),
            below=CascadeLink(_SETTLEMENT_SKELETON_ECONOMIC_TIER, ScopeLevel.SETTLEMENT),
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
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_WALL_MATERIAL, ScopeLevel.BUILDING),
        ),
        CascadeChannel(
            WALL_MATERIAL, ScopeLevel.BUILDING,
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_WALL_MATERIAL, ScopeLevel.AREA),
        ),
        CascadeChannel(
            WALL_MATERIAL, ScopeLevel.AREA,
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_WALL_MATERIAL, ScopeLevel.DISTRICT),
        ),
        CascadeChannel(
            WALL_MATERIAL, ScopeLevel.DISTRICT,
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_WALL_MATERIAL, ScopeLevel.SETTLEMENT),
        ),
        CascadeChannel(WALL_MATERIAL, ScopeLevel.SETTLEMENT),
    ] = None
    # `floor_material` chain — same shape (M9).
    parent_floor_material: Annotated[
        DefaultOnWire[MaterialKey | None],
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.ROOM,
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_FLOOR_MATERIAL, ScopeLevel.BUILDING),
        ),
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.BUILDING,
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_FLOOR_MATERIAL, ScopeLevel.AREA),
        ),
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.AREA,
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_FLOOR_MATERIAL, ScopeLevel.DISTRICT),
        ),
        CascadeChannel(
            FLOOR_MATERIAL, ScopeLevel.DISTRICT,
            below=CascadeLink(_BUNDLE_NAMED_LOCATION_PARENT_FLOOR_MATERIAL, ScopeLevel.SETTLEMENT),
        ),
        CascadeChannel(FLOOR_MATERIAL, ScopeLevel.SETTLEMENT),
    ] = None
    is_outdoor: DefaultOnWire[bool | None] = None
    is_sheltered: DefaultOnWire[bool] = False
    is_transit: DefaultOnWire[bool] = False
    created_at: DefaultOnWire[str | None] = None
    location_payload: DefaultOnWire[SettlementPayload | DistrictPayload | None] = None

    @model_validator(mode="before")
    @classmethod
    def bind_payload(cls, raw, info: ValidationInfo):
        if not isinstance(raw, dict):
            return raw
        values = dict(raw)
        registry = (info.context or {}).get("location_type_registry")
        if registry is None:
            registry = WorldLocationTypeRegistry.canonical_engine()
        system_type = values.get("system_location_type")
        entry = registry.entry_for(system_type) if isinstance(system_type, str) else None
        kind = entry.payload_kind if entry is not None else None
        nested = values.get("location_payload")
        if entry is None or kind is None:
            LocationPayload.validate(None, nested)
            return values
        model = LocationPayload.model_for(kind)
        payload = nested.model_dump() if isinstance(nested, BaseModel) else dict(nested or {})
        # Flat import keys and aliases remain the wire API. Pick only fields
        # declared by the chosen POJO, not a parallel list in the importer.
        for name, field in model.model_fields.items():
            aliases = (field.validation_alias.choices
                       if isinstance(field.validation_alias, AliasChoices) else ())
            for key in (name, *aliases):
                if key in values:
                    payload[name] = values[key]
                    break
        if "is_inhabited" in model.model_fields and "is_inhabited" not in payload:
            subtype = values.get("system_location_subtype")
            recipe = registry.subtype_for(entry.system_type, subtype) if isinstance(subtype, str) else None
            if recipe is not None:
                payload["is_inhabited"] = recipe.is_inhabited
        values["location_payload"] = model.model_validate(payload)
        return values

    architectural_style: DefaultOnWire[str | None] = _skeleton_default("architectural_style")
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
        payload_fields = {name for model in LocationPayload.models().values()
                          for name in model.model_fields}
        return self.model_dump(mode="json", exclude_none=True, exclude=payload_fields)
