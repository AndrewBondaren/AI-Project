from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Label, Nat

class CalendarPeriodRegistry(CalendarRecord):
    entries: StrictOnWire[tuple[PeriodEntry, ...]] = Field(min_length=1)

    def entry_for(self, key: Key[CalendarPeriodRegistry]) -> PeriodEntry | None:
        return next((entry for entry in self.entries if entry.system_period == key), None)

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.system_period for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate period key")
        return self


class PeriodEntry(CalendarRecord):
    system_period: StrictOnWire[Key[CalendarPeriodRegistry]]
    display_period: StrictOnWire[Label]
    from_hour: StrictOnWire[Nat]


CalendarPeriodRegistry.model_rebuild()
