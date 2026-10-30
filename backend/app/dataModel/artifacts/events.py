"""Staging/holder/GC event context for the project's shared logging facade."""

from enum import StrEnum
from pydantic import BaseModel, ConfigDict

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
