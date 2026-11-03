from __future__ import annotations

from pydantic import Field

from app.dataModel.world.calendar.catalogs.spans import CalendarSpanRegistry
from app.dataModel.world.calendar.catalogs.weekdays import CalendarWeekdayRegistry
from app.dataModel.world.calendar.catalogs.seasons import CalendarSeasonRegistry
from app.dataModel.world.calendar.catalogs.periods import CalendarPeriodRegistry
from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Label, Nat
from app.dataModel.world.calendar.enums.rules import CalendarNumbering, CalendarWeekMode
from app.dataModel.world.calendar.dates.anchor import CalendarAnchor
from app.dataModel.world.calendar.rules.edits import Edit, CalendarSpan
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import WorldCalendarRegistry


class CalendarDefinition(CalendarRecord):
    system_calendar: StrictOnWire[Key[WorldCalendarRegistry]]
    display_calendar: StrictOnWire[Label]
    description: StrictOnWire[str]
    numbering: StrictOnWire[CalendarNumbering]
    spans: StrictOnWire[CalendarSpanRegistry]
    weekdays: StrictOnWire[CalendarWeekdayRegistry]
    seasons: StrictOnWire[CalendarSeasonRegistry]
    periods: StrictOnWire[CalendarPeriodRegistry]
    base_year: StrictOnWire[tuple[CalendarSpan, ...]] = Field(min_length=1)
    rules: StrictOnWire[tuple[Edit, ...]]
    week_mode: StrictOnWire[CalendarWeekMode]
    week_anchor_ordinal: StrictOnWire[int]
    week_anchor_index: StrictOnWire[Nat]


class CalendarEntry(CalendarRecord):
    definition: StrictOnWire[CalendarDefinition]
    anchor: StrictOnWire[CalendarAnchor]
