"""One `worlds.lore_registry` map value — N1-W-21 stub body."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire


class LoreRegistryEntry(BaseModel):
    """tz_json_validation.md N1-W-21 — glossary target; full contract deferred to tz_lore."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    display_name: StrictOnWire[str] = Field(
        validation_alias=AliasChoices("display_name", "title"),
    )
    description: OptionalOnWire[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("description", "content"),
    )
