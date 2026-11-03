from typing import Protocol

from app.application.time.pure.arithmetic import TimeArithmetic
from app.dataModel.time.changes.advance import PrepareAdvance, TimeAdvanceProposal
from app.dataModel.time.operations.arithmetic import AddDurationInput
from app.dataModel.time.results.errors import TimeAdvanceMustBePositive, TimeRangeOverflow
from app.dataModel.time.values.interval import TimeInterval


class ITimeAdvancePipelineOpenPipeline(Protocol):
    def prepare_advance(self, request: PrepareAdvance) -> TimeAdvanceProposal | TimeAdvanceMustBePositive | TimeRangeOverflow: ...


class TimeAdvancePipelineOpenPipeline:
    def prepare_advance(self, request: PrepareAdvance) -> TimeAdvanceProposal | TimeAdvanceMustBePositive | TimeRangeOverflow:
        duration = request.duration
        if duration.seconds == duration.nanoseconds == 0:
            return TimeAdvanceMustBePositive(duration=duration)
        start = request.base.point
        result = TimeArithmetic.add(AddDurationInput(point=start, duration=duration))
        if isinstance(result, TimeRangeOverflow):
            return result
        return TimeAdvanceProposal(operation_id=request.operation_id, base=request.base,
                                   interval=TimeInterval(start=start, end=result.point))
