"""Pregame publication outcomes share bookkeeping, not snapshot ticks."""

from enum import StrEnum
from typing import Literal, NamedTuple, Self
from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef


class PackActivationDisposition(StrEnum):
    ACTIVE = "active"
    READY_INACTIVE = "ready_inactive"


class CasDecision(StrEnum):
    APPLIED = "applied"
    MISMATCH = "mismatch"


class ObservedPublication(NamedTuple):
    publication_id: EntityUid
    operation_id: EntityUid | None


class WorldCasMismatch(NamedTuple):
    operation_id: EntityUid
    expected: WorldPublicationRef
    observed: WorldPublicationRef
    publication: ObservedPublication
    differing_fields: tuple[str, ...]


class PlayerCasMismatch(NamedTuple):
    operation_id: EntityUid
    expected: PlayerHeadExpectation
    observed: PlayerSnapshotRef | None
    publication: ObservedPublication | None


WorldCasResult = Literal[CasDecision.APPLIED] | WorldCasMismatch
PlayerCasResult = Literal[CasDecision.APPLIED] | PlayerCasMismatch


class CasStep(NamedTuple):
    operation_id: EntityUid
    target: WorldPublicationRef | PlayerSnapshotRef
    decision: CasDecision


class CasConflictTrace(NamedTuple):
    mismatch: WorldCasMismatch | PlayerCasMismatch
    steps: tuple[CasStep, ...]


class PackActivationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    operation_id: EntityUid
    request_fingerprint: RevisionHex
    manifest: ArtifactRef
    disposition: PackActivationDisposition
    publication: WorldPublicationRef

    @model_validator(mode="after")
    def coherent_activation(self) -> Self:
        if self.disposition is PackActivationDisposition.ACTIVE:
            if self.publication.gameplay_started or self.publication.pack_hash != self.manifest.content_hash:
                raise ValueError("active pregame manifest must match the publication pack")
        # READY_INACTIVE may observe a competing gameplay-start publication.
        return self


class GameplayStarted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    operation_id: EntityUid
    request_fingerprint: RevisionHex
    publication: WorldPublicationRef

    @model_validator(mode="after")
    def coherent_start(self) -> Self:
        if not self.publication.gameplay_started or self.publication.snapshot_head is not None:
            raise ValueError("gameplay start requires the guard without a snapshot tick")
        return self
