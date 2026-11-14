"""Snapshot-owned relation diagnostics; no synthetic field paths."""
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.registry.sectionMetadata import SectionKey


class SnapshotApplyCode(StrEnum):
    OPERATION_BINDING_MISMATCH = "snapshot.apply.operation_binding_mismatch"
    UNSUPPORTED_REQUEST_FORMAT = "snapshot.apply.unsupported_request_format"
    SECTION_BINDING_MISMATCH = "snapshot.apply.section_binding_mismatch"
    DEPENDENCY_MISMATCH = "snapshot.apply.dependency_mismatch"
    WORLD_EXPECTATION_MISMATCH = "snapshot.apply.world_expectation_mismatch"
    PLAYER_EXPECTATION_MISMATCH = "snapshot.apply.player_expectation_mismatch"
    GAMEPLAY_NOT_STARTED = "snapshot.apply.gameplay_not_started"
    ACTIVE_TIMELINE_MISMATCH = "snapshot.apply.active_timeline_mismatch"
    TURN_SEQUENCE_MISMATCH = "snapshot.apply.turn_sequence_mismatch"
    ARTIFACT_UNAVAILABLE = "snapshot.apply.artifact_unavailable"


class SnapshotApplyRelationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    code: SnapshotApplyCode
    section_key: SectionKey | None
    player_uid: EntityUid | None
    artifact: ArtifactRef | None

    @model_validator(mode="after")
    def exact_context(self) -> Self:
        section = self.code in (SnapshotApplyCode.SECTION_BINDING_MISMATCH, SnapshotApplyCode.DEPENDENCY_MISMATCH)
        player = self.code is SnapshotApplyCode.PLAYER_EXPECTATION_MISMATCH
        artifact = self.code is SnapshotApplyCode.ARTIFACT_UNAVAILABLE
        if ((self.section_key is not None) != section or (self.player_uid is not None) != player
                or (self.artifact is not None) != artifact):
            raise ValueError("apply issue context must match its code")
        return self
