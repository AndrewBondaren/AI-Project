"""Typed events for the shared logging domain; delivery belongs to application."""

from enum import StrEnum
from typing import Self
from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind


class SnapshotLogActivity(StrEnum):
    APPLY_STARTED = "apply_started"
    APPLY_COMMITTED = "apply_committed"
    APPLY_CONFLICT = "apply_conflict"
    APPLY_REJECTED = "apply_rejected"
    APPLY_FAILED = "apply_failed"
    APPLY_OUTCOME_UNKNOWN = "apply_outcome_unknown"
    OPERATION_BUSY = "operation_busy"
    OPERATION_RECOVERED = "operation_recovered"


class SnapshotLogRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    activity: SnapshotLogActivity
    operation_id: EntityUid
    world_uid: EntityUid
    request_fingerprint: RevisionHex | None
    timeline_id: EntityUid | None
    snapshot_id: EntityUid | None
    section_key: SectionKey | None
    outcome: SnapshotApplyOutcomeKind | None

    @model_validator(mode="after")
    def coherent_outcome(self) -> Self:
        expected = {
            SnapshotLogActivity.APPLY_COMMITTED: SnapshotApplyOutcomeKind.COMMITTED,
            SnapshotLogActivity.APPLY_CONFLICT: SnapshotApplyOutcomeKind.CONFLICT,
            SnapshotLogActivity.APPLY_REJECTED: SnapshotApplyOutcomeKind.REJECTED,
        }
        if self.activity in expected:
            if self.outcome is not expected[self.activity] or self.request_fingerprint is None:
                raise ValueError("outcome activity requires matching outcome and request binding")
        elif self.activity is not SnapshotLogActivity.OPERATION_RECOVERED and self.outcome is not None:
            raise ValueError("non-outcome activity cannot assert an apply outcome")
        return self
