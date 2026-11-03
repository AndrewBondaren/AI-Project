from app.dataModel.world.settings.timeOperations.read import (
    HistoricalTimeSettingsCapture, HistoricalTimeSettingsRead, TimeSettingsCapture, TimeSettingsRead,
)
from app.dataModel.world.settings.timeOperations.results import SettingsConflict, SettingsNotFound, SettingsSnapshotNotFound
from app.dataModel.world.settings.timeOperations.results import SettingsInvalid
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.world.settings.timeOperations.read import ResolveCalendarAt
from app.dataModel.world.calendar.projection.request import ResolvedCalendarAt
from .sourcePort import IWorldTimeSettingsSource


class WorldTimeSettingsReader:
    def __init__(self, source: IWorldTimeSettingsSource):
        self._source = source

    async def read_current(self, request: TimeSettingsRead) -> TimeSettingsCapture | SettingsConflict | SettingsNotFound:
        return await self._source.read_current(request)

    async def read_historical(self, request: HistoricalTimeSettingsRead) -> HistoricalTimeSettingsCapture | SettingsNotFound | SettingsSnapshotNotFound:
        return await self._source.read_historical(request)


class WorldCalendarResolver:
    @staticmethod
    def resolve_at(request: ResolveCalendarAt) -> ResolvedCalendarAt | SettingsInvalid:
        capture = request.capture
        for version in capture.versions:
            if version.calendar_key == request.calendar:
                return ResolvedCalendarAt(source=capture.source, version=version, settings=capture.settings)
        return SettingsInvalid(issues=(FieldPathError(path=("calendar",), message="unknown calendar"),))
