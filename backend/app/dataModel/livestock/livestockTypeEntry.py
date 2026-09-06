"""One `worlds.livestock_registry[]` row — N1-W-12. Livestock subjects."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire, StrictOnWire
from app.dataModel.livestock.enums.livestockKind import LivestockKind


class LivestockTypeEntry(BaseModel):
    """Husbandry instance. Kind is engine-closed purpose; key is N+1."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_livestock: StrictOnWire[str]
    livestock_kind: StrictEnumOnWire[LivestockKind]
    display_name: DefaultOnWire[str | None] = None
    glossary_ref: DefaultOnWire[str | None] = None
