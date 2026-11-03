from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Label
from app.dataModel.world.calendar.enums.rules import CalendarSpanRole

class CalendarSpanRegistry(CalendarRecord):
    entries: StrictOnWire[tuple[SpanEntry, ...]] = Field(min_length=1)

    def entry_for(self, key: Key[CalendarSpanRegistry]) -> SpanEntry | None:
        return next((entry for entry in self.entries if entry.system_span == key), None)

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.system_span for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate span key")
        return self


class SpanEntry(CalendarRecord):
    system_span: StrictOnWire[Key[CalendarSpanRegistry]]
    display_span: StrictOnWire[Label]
    role: StrictOnWire[CalendarSpanRole]


CalendarSpanRegistry.model_rebuild()
