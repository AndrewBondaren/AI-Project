from typing import Self

from pydantic import model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.storage.initial import InitialTimeFacts
from app.dataModel.time.storage.state import StoredTimeState
from app.dataModel.time.values.point import TimeRecord


class BindInitialTime(TimeRecord):
    world_uid: EntityUid
    timeline_id: EntityUid
    initial: InitialTimeFacts

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.world_uid != self.initial.world_uid:
            raise ValueError("initial facts belong to another world")
        return self


class RebindBranchTime(TimeRecord):
    source: StoredTimeState
    target_timeline_id: EntityUid

    @model_validator(mode="after")
    def distinct_branch(self) -> Self:
        if self.target_timeline_id == self.source.state.point.timeline_id:
            raise ValueError("target must be a new timeline")
        return self
