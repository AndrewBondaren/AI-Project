from __future__ import annotations

from typing import Self

from pydantic import model_validator

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Label

class CalendarSeasonRegistry(CalendarRecord):
    entries: StrictOnWire[tuple[SeasonEntry, ...]]

    def entry_for(self, key: Key[CalendarSeasonRegistry]) -> SeasonEntry | None:
        return next((entry for entry in self.entries if entry.system_season == key), None)

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.system_season for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate season key")
        return self


class SeasonEntry(CalendarRecord):
    system_season: StrictOnWire[Key[CalendarSeasonRegistry]]
    display_season: StrictOnWire[Label]


CalendarSeasonRegistry.model_rebuild()
