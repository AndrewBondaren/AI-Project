from typing import Self

from pydantic import model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.time.values.duration import TimeDuration
from app.dataModel.time.values.interval import TimeInterval
from app.dataModel.time.values.point import TimeRecord


class PrepareAdvance(TimeRecord):
    operation_id: EntityUid
    base: TimeCapture
    duration: TimeDuration


class TimeAdvanceProposal(TimeRecord):
    operation_id: EntityUid
    base: TimeCapture
    interval: TimeInterval

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.interval.start != self.base.point or self.interval.end == self.interval.start:
            raise ValueError("advance must start at base and have positive duration")
        return self
