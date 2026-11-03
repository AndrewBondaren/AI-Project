from enum import StrEnum

from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.values.point import TimePoint, TimeRecord
from app.dataModel.time.values.duration import TimeDuration
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class TimeArithmeticKind(StrEnum):
    ADD = "add"
    DIFFERENCE = "difference"
    HOURS_TO_DURATION = "hours_to_duration"


class TimeUnavailableReason(StrEnum):
    WORLD_MISSING = "world_missing"
    CLOCK_UNINITIALIZED = "clock_uninitialized"
    SNAPSHOT_MISSING = "snapshot_missing"
    SOURCE_UNRESOLVED = "source_unresolved"


class TimeScopeMismatch(TimeRecord):
    left: TimePoint
    right: TimePoint


class TimeRangeOverflow(TimeRecord):
    operation: TimeArithmeticKind


class TimeIntervalReversed(TimeRecord):
    start: TimePoint
    end: TimePoint


class TimeAdvanceMustBePositive(TimeRecord):
    duration: TimeDuration


class TimePublicationConflict(TimeRecord):
    expected: WorldPublicationRef
    observed: WorldPublicationRef


class TimeInactiveTimeline(TimeRecord):
    requested: EntityUid
    active: EntityUid | None


class TimeStateUnavailable(TimeRecord):
    world_uid: EntityUid
    reason: TimeUnavailableReason
