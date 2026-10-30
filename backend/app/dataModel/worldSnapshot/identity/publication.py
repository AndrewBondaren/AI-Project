"""Captured publication expectations; CAS and ancestry checks belong to ports."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, WorldSnapshotRef


class WorldPublicationRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    world_uid: EntityUid
    publication_id: EntityUid
    pack_hash: RevisionHex | None
    snapshot_head: WorldSnapshotRef | None
    active_timeline_id: EntityUid | None
    gameplay_started: bool

    @model_validator(mode="after")
    def coherent_refs(self) -> Self:
        if self.snapshot_head is not None:
            if self.snapshot_head.world_uid != self.world_uid:
                raise ValueError("snapshot head belongs to another world")
            if not self.gameplay_started:
                raise ValueError("a snapshot head requires started gameplay")
        if self.gameplay_started and (self.pack_hash is None or self.active_timeline_id is None):
            raise ValueError("started gameplay requires a pack and active timeline")
        # A head from another timeline may be a pinned branch point. The
        # publication guard verifies that ancestry; this record performs no IO.
        return self


class PlayerHeadExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    player_uid: EntityUid
    expected_head: PlayerSnapshotRef | None

    @model_validator(mode="after")
    def coherent_refs(self) -> Self:
        if self.expected_head is not None and self.expected_head.player_uid != self.player_uid:
            raise ValueError("snapshot head belongs to another player")
        return self
