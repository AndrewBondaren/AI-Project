from typing import Self

from pydantic import model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.world.calendar.definitions.definition import CalendarEntry
from app.dataModel.world.calendar.epochs.epoch import WorldCalendarEpoch
from app.dataModel.world.calendar.epochs.registry import WorldCalendarEpochRegistry
from app.dataModel.world.calendar.dates.anchor import CalendarOrigin
from app.dataModel.world.calendar.projection.request import CalendarBudget
from .read import TimeSettingsCapture
from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Pos
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry


class SettingsPreparationBase(CalendarRecord):
    operation_id: EntityUid
    capture: TimeSettingsCapture
    clock: TimeCapture
    budget: CalendarBudget

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.clock.publication != self.capture.source:
            raise ValueError("settings and clock require the same publication")
        return self


class CalendarAnchorReplacement(CalendarRecord):
    calendar: Key[WorldCalendarRegistry]
    origin: CalendarOrigin


class HoursChange(CalendarRecord):
    base: SettingsPreparationBase
    hours_per_day: Pos
    anchors: tuple[CalendarAnchorReplacement, ...]


class CalendarCreate(CalendarRecord):
    base: SettingsPreparationBase
    entry: CalendarEntry


class CalendarUpdate(CalendarRecord):
    base: SettingsPreparationBase
    entry: CalendarEntry


class CalendarSelect(CalendarRecord):
    base: SettingsPreparationBase
    calendar: Key[WorldCalendarRegistry]


class CalendarRemove(CalendarRecord):
    base: SettingsPreparationBase
    calendar: Key[WorldCalendarRegistry]
    replacement: Key[WorldCalendarRegistry]


class EpochCreate(CalendarRecord):
    base: SettingsPreparationBase
    epoch: WorldCalendarEpoch


class EpochUpdate(CalendarRecord):
    base: SettingsPreparationBase
    epoch: WorldCalendarEpoch


class EpochRemove(CalendarRecord):
    base: SettingsPreparationBase
    epoch: Key[WorldCalendarEpochRegistry]
