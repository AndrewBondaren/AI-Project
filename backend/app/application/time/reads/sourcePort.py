from typing import Protocol

from app.dataModel.time.reads.capture import HistoricalTimeCapture, TimeCapture
from app.dataModel.time.reads.request import CurrentTimeRead, HistoricalTimeRead
from app.dataModel.time.results.errors import TimeInactiveTimeline, TimePublicationConflict, TimeStateUnavailable


class ITimeReadSource(Protocol):
    async def read_current(self, request: CurrentTimeRead) -> TimeCapture | TimePublicationConflict | TimeInactiveTimeline | TimeStateUnavailable: ...

    async def read_historical(self, request: HistoricalTimeRead) -> HistoricalTimeCapture | TimeStateUnavailable: ...
