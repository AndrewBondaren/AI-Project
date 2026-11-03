from typing import Self

from pydantic import model_validator

from .point import TimePoint, TimeRecord


class TimeInterval(TimeRecord):
    start: TimePoint
    end: TimePoint

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.start.scope != self.end.scope or self.end.coordinate < self.start.coordinate:
            raise ValueError("interval requires ordered points in one scope")
        return self
