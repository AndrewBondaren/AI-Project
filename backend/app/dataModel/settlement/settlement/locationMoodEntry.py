"""One `worlds.location_mood_registry[]` row."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.registryKey import RegistryKey

if TYPE_CHECKING:
    from app.dataModel.settlement.settlement.worldLocationMoodRegistry import (
        WorldLocationMoodRegistry,
    )


class LocationMoodEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_mood: StrictOnWire[RegistryKey[WorldLocationMoodRegistry]]
    display_mood: DefaultOnWire[str | None] = None
