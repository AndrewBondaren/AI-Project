from typing import Self

from pydantic import model_validator

from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.time.values.point import TimePoint, TimeRecord


def validate_publication_point(source: WorldPublicationRef, point: TimePoint) -> None:
    if (not source.gameplay_started or source.world_uid != point.world_uid
            or source.active_timeline_id != point.timeline_id):
        raise ValueError("point must belong to the active publication scope")


class TimeCapture(TimeRecord):
    publication: WorldPublicationRef
    point: TimePoint

    @model_validator(mode="after")
    def coherent(self) -> Self:
        validate_publication_point(self.publication, self.point)
        return self


class HistoricalTimeCapture(TimeRecord):
    snapshot: WorldSnapshotRef
    point: TimePoint

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.snapshot.world_uid != self.point.world_uid or self.snapshot.timeline_id != self.point.timeline_id:
            raise ValueError("point must belong to the snapshot scope")
        return self
