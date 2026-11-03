from app.dataModel.time.operations.arithmetic import DurationResult
from app.dataModel.time.operations.conversion import HoursInput, SecondsInput
from app.dataModel.time.results.errors import TimeArithmeticKind, TimeRangeOverflow
from app.dataModel.time.values.duration import TimeDuration
from app.dataModel.time.values.point import MAX_SECONDS


class TimeConversions:
    @staticmethod
    def from_seconds(request: SecondsInput) -> DurationResult:
        return DurationResult(duration=TimeDuration(seconds=request.seconds, nanoseconds=request.nanoseconds))

    @staticmethod
    def from_hours(request: HoursInput) -> DurationResult | TimeRangeOverflow:
        seconds = request.hours * 3600
        if seconds > MAX_SECONDS:
            return TimeRangeOverflow(operation=TimeArithmeticKind.HOURS_TO_DURATION)
        return DurationResult(duration=TimeDuration(seconds=seconds, nanoseconds=0))
