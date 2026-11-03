from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key

from . import definition as _entry_module
from .definition import CalendarEntry


class WorldCalendarRegistry(CalendarRecord):
    entries: StrictOnWire[tuple[CalendarEntry, ...]] = Field(min_length=1)

    def entry_for(self, key: Key[WorldCalendarRegistry]) -> CalendarEntry | None:
        return next((entry for entry in self.entries if entry.definition.system_calendar == key), None)

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.definition.system_calendar for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate registry key")
        return self


_entry_module.WorldCalendarRegistry = WorldCalendarRegistry
_entry_module.CalendarDefinition.model_rebuild()
CalendarEntry.model_rebuild()
WorldCalendarRegistry.model_rebuild()
