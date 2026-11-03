from __future__ import annotations

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Label
from app.dataModel.time.values.point import I64, Nano
from ..definitions.registry import WorldCalendarRegistry
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import WorldCalendarEpochRegistry


class WorldCalendarEpoch(CalendarRecord):
    system_epoch: StrictOnWire[Key[WorldCalendarEpochRegistry]]
    display_epoch: StrictOnWire[Label]
    description: StrictOnWire[str]
    calendar: StrictOnWire[Key[WorldCalendarRegistry]]
    start_seconds: StrictOnWire[I64]
    start_nanoseconds: StrictOnWire[Nano]
    start_year_label: StrictOnWire[int]
