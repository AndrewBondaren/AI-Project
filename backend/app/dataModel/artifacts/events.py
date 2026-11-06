"""Staging/holder/GC event context for the project's shared logging facade."""

from enum import StrEnum
from typing import Self
from pydantic import BaseModel, ConfigDict, model_validator
from app.dataModel.artifacts.lifecycle.gc import ArtifactGcFailure

from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class ArtifactLogActivity(StrEnum):
    ARTIFACT_SEALED = "artifact_sealed"
    LEASE_RELEASED = "lease_released"
    GC_DELETED = "gc_deleted"
    GC_FAILED = "gc_failed"


class ArtifactLogRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    activity: ArtifactLogActivity
    operation_id: EntityUid
    world_uid: EntityUid | None
    preparation_fingerprint: RevisionHex | None
    request_fingerprint: RevisionHex | None
    artifact_hash: RevisionHex | None
    gc_failure: ArtifactGcFailure | None = None

    @model_validator(mode="after")
    def failure_matches_activity(self) -> Self:
        if self.activity is ArtifactLogActivity.GC_FAILED:
            if self.gc_failure is None or self.artifact_hash != self.gc_failure.ref.content_hash:
                raise ValueError("GC_FAILED requires matching failure metadata")
        elif self.gc_failure is not None:
            raise ValueError("failure metadata is only valid for GC_FAILED")
        return self
