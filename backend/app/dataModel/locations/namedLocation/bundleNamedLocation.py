"""Bundle `locations[]` row — master wire before `NamedLocation` persist."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, IgnoreOnWire, StrictOnWire


class BundleNamedLocation(BaseModel):
    """tz_locations.md § named_locations — import wire contract."""

    model_config = ConfigDict(extra="ignore", frozen=True)

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
    system_location_mood: DefaultOnWire[str | None] = None
    display_location_mood: DefaultOnWire[str | None] = None
    owner_uid: DefaultOnWire[str | None] = None
    system_climate_zone: DefaultOnWire[str | None] = None
    state_uid: DefaultOnWire[str | None] = None
    system_city_size: DefaultOnWire[str | None] = None
    system_economic_tier: DefaultOnWire[str | None] = None
    is_public: DefaultOnWire[bool] = False
    is_forbidden: DefaultOnWire[bool] = False
    is_selectable: DefaultOnWire[bool] = True
    map_x: DefaultOnWire[int | None] = None
    map_y: DefaultOnWire[int | None] = None
    map_z: DefaultOnWire[int | None] = None
    is_mobile: DefaultOnWire[bool] = False
    system_template_uid: DefaultOnWire[str | None] = None
    parent_wall_material: DefaultOnWire[str | None] = None
    parent_floor_material: DefaultOnWire[str | None] = None
    is_outdoor: DefaultOnWire[bool | None] = None
    is_sheltered: DefaultOnWire[bool] = False
    is_transit: DefaultOnWire[bool] = False
    created_at: DefaultOnWire[str | None] = None

    def to_db_fields(self) -> dict[str, Any]:
        """Wire → ``NamedLocation`` kwargs."""
        return self.model_dump(exclude_none=True)
