from enum import StrEnum

from app.dataModel.time.values.point import TimePoint, TimeRecord
from app.dataModel.time.values.duration import TimeDuration
from app.dataModel.time.values.interval import TimeInterval


class TimeOrder(StrEnum):
    BEFORE = "before"
    EQUAL = "equal"
    AFTER = "after"


class AddDurationInput(TimeRecord):
    point: TimePoint
    duration: TimeDuration


class ComparePointsInput(TimeRecord):
    left: TimePoint
    right: TimePoint


class MakeIntervalInput(TimeRecord):
    start: TimePoint
    end: TimePoint


class PointResult(TimeRecord):
    point: TimePoint


class DurationResult(TimeRecord):
    duration: TimeDuration


class IntervalResult(TimeRecord):
    interval: TimeInterval


class ComparisonResult(TimeRecord):
    order: TimeOrder
