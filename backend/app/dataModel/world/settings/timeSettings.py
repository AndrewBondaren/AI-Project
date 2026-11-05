from typing import ClassVar

from app.dataModel.world.calendar.dates.anchor import CalendarOrigin
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.world.calendar.catalogs.periods import PeriodEntry

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Pos
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.calendar.epochs.registry import WorldCalendarEpochRegistry


class WorldTimeSettings(CalendarRecord):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-TIME-SETTINGS-V1"
    WIRE_RUNTIME_DEFAULTS: ClassVar = (
        FieldRef(lambda: WorldTimeSettings, lambda model: model.hours_per_day),
        FieldRef(lambda: PeriodEntry, lambda model: model.from_minute),
    )

    hours_per_day: DefaultWhenMissing[Pos] = 24
    calendars: StrictOnWire[WorldCalendarRegistry]
    selected: StrictOnWire[Key[WorldCalendarRegistry]]
    epochs: StrictOnWire[WorldCalendarEpochRegistry]

    @classmethod
    def standard(cls, hours_per_day: Pos, origin: CalendarOrigin) -> "WorldTimeSettings":
        from .standard.gregorian import standard_entry

        entry = standard_entry(hours_per_day, origin)
        return cls(hours_per_day=hours_per_day, selected=entry.definition.system_calendar,
                   calendars=WorldCalendarRegistry(entries=(entry,)), epochs=WorldCalendarEpochRegistry(entries=()))
