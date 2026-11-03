from typing import Self

from pydantic import model_validator

from app.dataModel.time.values.point import TimePoint, TimeRecord
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef


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
