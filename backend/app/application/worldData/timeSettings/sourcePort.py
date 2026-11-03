from typing import Protocol

from app.dataModel.world.settings.timeOperations.read import (
    HistoricalTimeSettingsCapture, HistoricalTimeSettingsRead, TimeSettingsCapture, TimeSettingsRead,
)
from app.dataModel.world.settings.timeOperations.results import SettingsConflict, SettingsNotFound, SettingsSnapshotNotFound


class IWorldTimeSettingsSource(Protocol):
    async def read_current(self, request: TimeSettingsRead) -> TimeSettingsCapture | SettingsConflict | SettingsNotFound: ...

    async def read_historical(self, request: HistoricalTimeSettingsRead) -> HistoricalTimeSettingsCapture | SettingsNotFound | SettingsSnapshotNotFound: ...
