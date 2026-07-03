"""One `worlds.location_mood_registry[]` row."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class LocationMoodEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_mood: StrictOnWire[str]
    display_mood: DefaultOnWire[str | None] = None
