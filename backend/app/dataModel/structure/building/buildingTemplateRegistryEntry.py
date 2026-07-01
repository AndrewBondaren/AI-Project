"""One `worlds.building_template_registry[]` row — per-world import pointer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.policy import OptionalOnWire, StrictOnWire


class BuildingTemplateRegistryEntry(BaseModel):
    """tz_building_generator.md §5.2 — uid pointer into global `building_templates`."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_template_uid: StrictOnWire[str]
    display_template_name: OptionalOnWire[str | None] = None
    imported_at: OptionalOnWire[str | None] = None
