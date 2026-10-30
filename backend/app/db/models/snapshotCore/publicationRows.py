"""Immutable SQL rows for Snapshot core; no publication behavior or IO."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorldPublicationRow:
    __table__ = "world_publications"
    __pk__ = "publication_id"

    publication_id: str
    world_uid: str
    predecessor_id: str | None
    publication_seq: int
    operation_id: str | None
    pack_hash: str | None
    snapshot_head_id: str | None
    active_timeline_id: str | None
    gameplay_started: bool = field(metadata={"db_type": "bool"})


@dataclass(frozen=True)
class PlayerPublicationRow:
    __table__ = "player_publications"
    __pk__ = "publication_id"

    publication_id: str
    player_uid: str
    predecessor_id: str | None
    publication_seq: int
    player_snapshot_id: str
    operation_id: str
