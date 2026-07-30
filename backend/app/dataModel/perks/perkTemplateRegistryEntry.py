"""One ``worlds.perk_template_registry[]`` pointer — tz_world_bundle WB-14."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class PerkTemplateRegistryEntry(BaseModel):
    """Per-world import pointer (bodies live in ``perk_templates`` library)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_template_uid: StrictOnWire[str]
    display_template_name: DefaultOnWire[str | None] = None
    imported_at: DefaultOnWire[str | None] = None
