from app.dataModel.world.calendar.scalars import CalendarRecord, Key
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from pydantic import Field
from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.values.point import TimePoint
from app.dataModel.world.calendar.projection.errors import CalendarFieldIssue
from app.dataModel.world.calendar.dates.clock import CalendarClockTime


class PreparedTimeSettingsChange(CalendarRecord):
    operation_id: EntityUid
    expected: WorldPublicationRef
    before: WorldTimeSettings
    after: WorldTimeSettings
    effective_at: TimePoint


class SettingsConflict(CalendarRecord):
    expected: WorldPublicationRef
    observed: WorldPublicationRef


class SettingsNotFound(CalendarRecord):
    world_uid: EntityUid


class SettingsSnapshotNotFound(CalendarRecord):
    snapshot: WorldSnapshotRef


class SettingsInvalid(CalendarRecord):
    issues: tuple[CalendarFieldIssue, ...] = Field(min_length=1)


class SettingsAnchorRequired(CalendarRecord):
    calendar: Key[WorldCalendarRegistry]
    current: CalendarClockTime


class SettingsInUse(CalendarRecord):
    calendar: Key[WorldCalendarRegistry]
