"""Immutable operation observations, not a state machine or publication entry."""

from typing import Annotated, Self
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.publication import GameplayStarted, PackActivationResult


class OperationCancelled(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    operation_id: EntityUid
    reason: FieldPathError


class OperationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    operation_id: EntityUid
    world_uid: EntityUid
    kind: OperationKind
    preparation_fingerprint: RevisionHex
    publication_fingerprint: RevisionHex | None
    phase: OperationPhase
    fence: Annotated[StrictInt, Field(ge=1)]
    leased_artifacts: tuple[ArtifactRef, ...]
    terminal: SnapshotApplyResult | PackActivationResult | GameplayStarted | OperationCancelled | None

    @model_validator(mode="after")
    def coherent_record(self) -> Self:
        if (self.phase is OperationPhase.TERMINAL) != (self.terminal is not None):
            raise ValueError("only terminal phase requires a terminal result")
        if self.phase is OperationPhase.APPLYING and self.publication_fingerprint is None:
            raise ValueError("applying requires the publication binding")
        if len(set(self.leased_artifacts)) != len(self.leased_artifacts):
            raise ValueError("duplicate leased artifact")
        result = self.terminal
        if result is None:
            return self
        if result.operation_id != self.operation_id:
            raise ValueError("terminal belongs to another operation")
        if isinstance(result, OperationCancelled):
            return self
        if result.request_fingerprint != self.publication_fingerprint:
            raise ValueError("terminal does not match the publication binding")
        if isinstance(result, SnapshotApplyResult):
            if result.category is SnapshotApplyOutcomeKind.COMMITTED:
                if self.kind is not OperationKind.SNAPSHOT_APPLY:
                    raise ValueError("only snapshot apply can commit snapshot refs")
                if result.committed is not None and result.committed.world_snapshot.world_uid != self.world_uid:
                    raise ValueError("committed snapshot belongs to another world")
        else:
            if isinstance(result, PackActivationResult) and self.kind is not OperationKind.PACK_ACTIVATION:
                raise ValueError("activation outcome requires pack activation kind")
            if isinstance(result, GameplayStarted) and self.kind is not OperationKind.GAMEPLAY_START:
                raise ValueError("gameplay outcome requires gameplay start kind")
            if result.publication.world_uid != self.world_uid:
                raise ValueError("terminal publication belongs to another world")
        return self
