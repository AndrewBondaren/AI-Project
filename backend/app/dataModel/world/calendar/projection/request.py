from app.dataModel.world.calendar.scalars import CalendarRecord, Key, Pos
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.time.values.point import TimePoint, TimeScope
from app.dataModel.time.reads.capture import HistoricalTimeCapture, TimeCapture
from app.dataModel.world.calendar.dates.date import CalendarDate
from app.dataModel.world.calendar.dates.clock import CalendarClockTime


class CalendarBudget(CalendarRecord):
    max_rule_checks: Pos
    max_year_patterns: Pos


class CalendarVersionRef(CalendarRecord):
    calendar_key: Key[WorldCalendarRegistry]
    publication: WorldPublicationRef


class ResolvedCalendarAt(CalendarRecord):
    source: WorldPublicationRef | WorldSnapshotRef
    version: CalendarVersionRef
    settings: WorldTimeSettings


class CalendarProjectionInput(CalendarRecord):
    point: TimePoint
    capture: TimeCapture | HistoricalTimeCapture
    calendar: Key[WorldCalendarRegistry]
    resolved: ResolvedCalendarAt
    budget: CalendarBudget


class CalendarResolveInput(CalendarRecord):
    resolved: ResolvedCalendarAt
    calendar: Key[WorldCalendarRegistry]
    date: CalendarDate
    time: CalendarClockTime
    scope: TimeScope
    budget: CalendarBudget


class ValidateCalendarInput(CalendarRecord):
    settings: WorldTimeSettings
    budget: CalendarBudget
