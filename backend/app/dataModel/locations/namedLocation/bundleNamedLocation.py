"""Bundle `locations[]` row — master wire before `NamedLocation` persist."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, IgnoreOnWire, StrictOnWire
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    ECONOMIC_TIER,
    FLOOR_MATERIAL,
    WALL_MATERIAL,
)
from app.dataModel.cascade.cascadeSpec import CascadeChannel, CascadeLink, FieldRef, RepeatScope
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.locations.settlement.district.districtTemplateEntry import (
    DistrictTemplateEntry,
)
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.locations.settlement.settlement.worldLocationMoodRegistry import LocationMoodKey
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.dataModel.locations.locationPayload import LocationPayload
from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload


# Selectors live outside Annotated so static checkers inspect attributes.
_ROOM_DEF_ECONOMIC_TIER = FieldRef(lambda: RoomDef, lambda pojo: pojo.economic_tier)
_BUNDLE_NAMED_LOCATION_SYSTEM_ECONOMIC_TIER = FieldRef(lambda: BundleNamedLocation, lambda pojo: pojo.system_economic_tier)
_PLOT_LAYOUT_TEMPLATE_ECONOMIC_TIER = FieldRef(lambda: PlotLayoutTemplate, lambda pojo: pojo.economic_tier)
_PLOT_LAYOUT_TEMPLATE_ECONOMIC_TIER_RANGE = FieldRef(lambda: PlotLayoutTemplate, lambda pojo: pojo.economic_tier_range)
_DISTRICT_TEMPLATE_ENTRY_ECONOMIC_TIER_RANGE = FieldRef(lambda: DistrictTemplateEntry, lambda pojo: pojo.economic_tier_range)
_SETTLEMENT_SKELETON_ECONOMIC_TIER = FieldRef(lambda: SettlementSkeleton, lambda pojo: pojo.economic_tier)


class BundleNamedLocation(BaseModel):
    """tz_locations.md § named_locations — import wire contract."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    location_uid: StrictOnWire[str]
    display_name: StrictOnWire[str]
    system_location_type: StrictOnWire[str]

    parent_location_uid: DefaultWhenMissing[str | None] = None
    system_location_subtype: DefaultWhenMissing[str | None] = None
    system_description: IgnoreOnWire[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("system_description", "description"),
    )
    display_description: IgnoreOnWire[str | None] = None
    glossary_ref: DefaultWhenMissing[str | None] = None
    tag_refs: DefaultWhenMissing[list[str] | None] = None
    is_discovered: DefaultWhenMissing[bool] = False
    is_accessible: DefaultWhenMissing[bool] = True
    entry_difficulty: DefaultWhenMissing[int | None] = None
    guard_level: DefaultWhenMissing[int | None] = None
    system_location_mood: DefaultWhenMissing[LocationMoodKey | None] = None
    display_location_mood: DefaultWhenMissing[str | None] = None
    owner_uid: DefaultWhenMissing[str | None] = None
    system_climate_zone: DefaultWhenMissing[str | None] = None
    state_uid: DefaultWhenMissing[str | None] = None
    # Cascade channels for `economic_tier` — the stamped/authored node at
    # four levels; each edge declared once, where imports allow
    # (tz_cascade_context §2). Neighbours on the other side of an edge
    # are materialized by the contract verifier.
    system_economic_tier: Annotated[
        DefaultWhenMissing[EconomyTierKey | None],
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
    ] = None
    is_public: DefaultWhenMissing[bool] = False
    is_forbidden: DefaultWhenMissing[bool] = False
    is_selectable: DefaultWhenMissing[bool] = True
    map_x: DefaultWhenMissing[int | None] = None
    map_y: DefaultWhenMissing[int | None] = None
    map_z: DefaultWhenMissing[int | None] = None
    is_mobile: DefaultWhenMissing[bool] = False
    system_template_uid: DefaultWhenMissing[str | None] = None
    # Repeat one NL field on each tag of the declared context scope path.
    parent_wall_material: Annotated[
        DefaultWhenMissing[MaterialKey | None],
        CascadeChannel(WALL_MATERIAL, RepeatScope.EVERY_TAG),
    ] = None
    parent_floor_material: Annotated[
        DefaultWhenMissing[MaterialKey | None],
        CascadeChannel(FLOOR_MATERIAL, RepeatScope.EVERY_TAG),
    ] = None
    is_outdoor: DefaultWhenMissing[bool | None] = None
    is_sheltered: DefaultWhenMissing[bool] = False
    is_transit: DefaultWhenMissing[bool] = False
    created_at: DefaultWhenMissing[str | None] = None
    location_payload: DefaultWhenMissing[SettlementPayload | DistrictPayload | None] = None

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
            payload["is_inhabited"] = (
                recipe.is_inhabited
                if recipe is not None and recipe.is_inhabited is not None
                else entry.is_inhabited
            )
        values["location_payload"] = model.model_validate(payload)
        return values

    def to_db_fields(self) -> dict[str, Any]:
        """Wire → ``NamedLocation`` kwargs."""
        return self.model_dump(mode="json", exclude_none=True)
