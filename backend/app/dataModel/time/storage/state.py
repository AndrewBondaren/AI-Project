from typing import Self
from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
from app.dataModel.registryKey import RegistryKey

from pydantic import model_validator

from app.dataModel.time.reads.capture import validate_publication_point
from app.dataModel.time.values.point import TimePoint, TimeRecord
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef


CLOCK_SECTION = RegistryKey[PatchSectionRegistry]("time_clock")
CLOCK_FORMAT = 1


class TimeClockState(TimeRecord):
    point: TimePoint


class StoredTimeState(TimeRecord):
    ref: SectionStateRef
    state: TimeClockState

    @model_validator(mode="after")
    def coherent(self) -> Self:
        snapshot = self.ref.snapshot
        point = self.state.point
        if (not isinstance(snapshot, WorldSnapshotRef) or snapshot.world_uid != point.world_uid
                or snapshot.timeline_id != point.timeline_id):
            raise ValueError("state must belong to its world snapshot")
        return self


class PublicationTimeState(TimeRecord):
    publication: WorldPublicationRef
    state: TimeClockState

    @model_validator(mode="after")
    def coherent(self) -> Self:
        validate_publication_point(self.publication, self.state.point)
        return self
