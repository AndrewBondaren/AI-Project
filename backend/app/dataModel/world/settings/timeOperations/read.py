from typing import Self

from pydantic import model_validator

from app.dataModel.world.calendar.projection.request import CalendarVersionRef
from app.dataModel.world.calendar.scalars import CalendarRecord, Key
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef


class TimeSettingsRead(CalendarRecord):
    expected: WorldPublicationRef


class HistoricalTimeSettingsRead(CalendarRecord):
    snapshot: WorldSnapshotRef

class _SettingsCapture[S: (WorldPublicationRef, WorldSnapshotRef)](CalendarRecord):
    source: S
    settings: WorldTimeSettings
    versions: tuple[CalendarVersionRef, ...]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        keys = {entry.definition.system_calendar for entry in self.settings.calendars.entries}
        if (len(self.versions) != len(keys) or keys != {ref.calendar_key for ref in self.versions}
                or any(ref.publication.world_uid != self.source.world_uid for ref in self.versions)):
            raise ValueError("calendar versions must cover the source world and registry")
        return self


class TimeSettingsCapture(_SettingsCapture[WorldPublicationRef]):
    pass


class HistoricalTimeSettingsCapture(_SettingsCapture[WorldSnapshotRef]):
    pass


class ResolveCalendarAt(CalendarRecord):
    capture: TimeSettingsCapture | HistoricalTimeSettingsCapture
    calendar: Key[WorldCalendarRegistry]
