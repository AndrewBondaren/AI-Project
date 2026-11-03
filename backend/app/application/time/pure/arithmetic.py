from app.dataModel.time.operations.arithmetic import (
    AddDurationInput, ComparePointsInput, ComparisonResult, DurationResult, IntervalResult,
    MakeIntervalInput, PointResult, TimeOrder,
)
from app.dataModel.time.results.errors import (
    TimeArithmeticKind, TimeIntervalReversed, TimeRangeOverflow, TimeScopeMismatch,
)
from app.dataModel.time.values.duration import TimeDuration
from app.dataModel.time.values.interval import TimeInterval
from app.dataModel.time.values.point import MAX_SECONDS, NANOS_PER_SECOND, TimePoint


class TimeArithmetic:
    @staticmethod
    def add(request: AddDurationInput) -> PointResult | TimeRangeOverflow:
        point, duration = request.point, request.duration
        carry, nanos = divmod(point.nanoseconds + duration.nanoseconds, NANOS_PER_SECOND)
        seconds = point.seconds + duration.seconds + carry
        if seconds > MAX_SECONDS:
            return TimeRangeOverflow(operation=TimeArithmeticKind.ADD)
        return PointResult(point=TimePoint(world_uid=point.world_uid, timeline_id=point.timeline_id,
                                           seconds=seconds, nanoseconds=nanos))

    @staticmethod
    def compare(request: ComparePointsInput) -> ComparisonResult | TimeScopeMismatch:
        left, right = request.left, request.right
        if left.scope != right.scope:
            return TimeScopeMismatch(left=left, right=right)
        if left.coordinate == right.coordinate:
            return ComparisonResult(order=TimeOrder.EQUAL)
        order = TimeOrder.BEFORE if left.coordinate < right.coordinate else TimeOrder.AFTER
        return ComparisonResult(order=order)

    @staticmethod
    def interval(request: MakeIntervalInput) -> IntervalResult | TimeScopeMismatch | TimeIntervalReversed:
        start, end = request.start, request.end
        if start.scope != end.scope:
            return TimeScopeMismatch(left=start, right=end)
        if end.coordinate < start.coordinate:
            return TimeIntervalReversed(start=start, end=end)
        return IntervalResult(interval=TimeInterval(start=start, end=end))

    @staticmethod
    def elapsed(interval: TimeInterval) -> DurationResult | TimeRangeOverflow:
        start, end = interval.start, interval.end
        carry, nanos = divmod(end.nanoseconds - start.nanoseconds, NANOS_PER_SECOND)
        seconds = end.seconds - start.seconds + carry
        if seconds > MAX_SECONDS:
            return TimeRangeOverflow(operation=TimeArithmeticKind.DIFFERENCE)
        return DurationResult(duration=TimeDuration(seconds=seconds, nanoseconds=nanos))
