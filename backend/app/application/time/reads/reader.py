from app.dataModel.time.reads.capture import HistoricalTimeCapture, TimeCapture
from app.dataModel.time.reads.request import CurrentTimeRead, HistoricalTimeRead
from app.dataModel.time.results.errors import TimeInactiveTimeline, TimePublicationConflict, TimeStateUnavailable
from .sourcePort import ITimeReadSource


class TimeReader:
    def __init__(self, source: ITimeReadSource):
        self._source = source

    async def read_current(self, request: CurrentTimeRead) -> TimeCapture | TimePublicationConflict | TimeInactiveTimeline | TimeStateUnavailable:
        return await self._source.read_current(request)

    async def read_historical(self, request: HistoricalTimeRead) -> HistoricalTimeCapture | TimeStateUnavailable:
        return await self._source.read_historical(request)
