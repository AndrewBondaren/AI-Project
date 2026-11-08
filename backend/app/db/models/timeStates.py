from dataclasses import dataclass


@dataclass(frozen=True)
class TimePublicationRow:
    __table__ = "time_publication_states"
    __pk__ = "publication_id"
    publication_id: str
    payload: str


@dataclass(frozen=True)
class TimeSnapshotRow:
    __table__ = "time_snapshot_states"
    __pk__ = "snapshot_id"
    snapshot_id: str
    payload: str
