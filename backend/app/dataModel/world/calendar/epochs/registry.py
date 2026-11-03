from __future__ import annotations

from typing import Self

from pydantic import model_validator

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key

from . import epoch as _entry_module
from .epoch import WorldCalendarEpoch


class WorldCalendarEpochRegistry(CalendarRecord):
    entries: StrictOnWire[tuple[WorldCalendarEpoch, ...]]

    def entry_for(self, key: Key[WorldCalendarEpochRegistry]) -> WorldCalendarEpoch | None:
        return next((entry for entry in self.entries if entry.system_epoch == key), None)

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.system_epoch for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate registry key")
        return self


_entry_module.WorldCalendarEpochRegistry = WorldCalendarEpochRegistry
WorldCalendarEpoch.model_rebuild()
WorldCalendarEpochRegistry.model_rebuild()
