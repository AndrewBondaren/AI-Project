"""One ``worlds.relief_template_registry[]`` row — pointer into global library."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire, StrictOnWire
from app.dataModel.terrain.relief.enums import ReliefContext


class ReliefTemplateRegistryEntry(BaseModel):
    """Per-world import pointer (bodies live in SQL library / bundle section)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_template_uid: StrictOnWire[str]
    display_template_name: DefaultOnWire[str | None] = None
    context: StrictEnumOnWire[ReliefContext]
    imported_at: DefaultOnWire[str | None] = None
