from __future__ import annotations

from typing import Self

from pydantic import model_validator

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Label

class CalendarWeekdayRegistry(CalendarRecord):
    entries: StrictOnWire[tuple[WeekdayEntry, ...]]

    def entry_for(self, key: Key[CalendarWeekdayRegistry]) -> WeekdayEntry | None:
        return next((entry for entry in self.entries if entry.system_weekday == key), None)

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.system_weekday for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate weekday key")
        return self


class WeekdayEntry(CalendarRecord):
    system_weekday: StrictOnWire[Key[CalendarWeekdayRegistry]]
    display_weekday: StrictOnWire[Label]


CalendarWeekdayRegistry.model_rebuild()
