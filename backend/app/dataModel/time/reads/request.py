from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.time.values.point import TimeRecord


class CurrentTimeRead(TimeRecord):
    expected: WorldPublicationRef


class HistoricalTimeRead(TimeRecord):
    snapshot: WorldSnapshotRef
