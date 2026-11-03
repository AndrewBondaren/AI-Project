from app.dataModel.world.calendar.scalars import CalendarRecord, Key
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.time.values.point import TimePoint
from app.dataModel.world.calendar.dates.date import CalendarDate
from app.dataModel.world.calendar.dates.clock import CalendarClockTime
from ..catalogs.weekdays import CalendarWeekdayRegistry
from ..catalogs.seasons import CalendarSeasonRegistry
from ..catalogs.periods import CalendarPeriodRegistry
from ..epochs.registry import WorldCalendarEpochRegistry
from .request import CalendarVersionRef


class CalendarProjection(CalendarRecord):
    point: TimePoint
    version: CalendarVersionRef
    date: CalendarDate
    time: CalendarClockTime
    weekday: Key[CalendarWeekdayRegistry] | None
    season: Key[CalendarSeasonRegistry] | None
    period: Key[CalendarPeriodRegistry]
    epoch: Key[WorldCalendarEpochRegistry] | None
    epoch_year: int | None


class CalendarValidated(CalendarRecord):
    settings: WorldTimeSettings
