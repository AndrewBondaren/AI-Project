"""Durable apply outcome data; no request, execution or persistence dependency."""

from typing import Self
from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind


class SnapshotCommitRefs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    world_snapshot: WorldSnapshotRef
    player_snapshots: tuple[PlayerSnapshotRef, ...]
    publication: WorldPublicationRef

    @model_validator(mode="after")
    def coherent_commit(self) -> Self:
        if (self.publication.snapshot_head != self.world_snapshot
                or self.publication.active_timeline_id != self.world_snapshot.timeline_id):
            raise ValueError("publication must point to the committed world snapshot and timeline")
        if len({ref.player_uid for ref in self.player_snapshots}) != len(self.player_snapshots):
            raise ValueError("duplicate committed player")
        return self


class SnapshotApplyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    category: SnapshotApplyOutcomeKind
    operation_id: EntityUid
    request_fingerprint: RevisionHex
    committed: SnapshotCommitRefs | None
    diagnostics: tuple[FieldPathError, ...]

    @model_validator(mode="after")
    def coherent_outcome(self) -> Self:
        if self.category is SnapshotApplyOutcomeKind.COMMITTED:
            if self.committed is None or self.diagnostics:
                raise ValueError("committed requires refs and no diagnostics")
        elif self.committed is not None or not self.diagnostics:
            raise ValueError("refusal requires diagnostics and no committed refs")
        return self
