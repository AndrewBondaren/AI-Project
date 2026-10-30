"""Captured staging capabilities; no lease acquisition or writer execution."""

from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class OperationLeaseRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    operation_id: EntityUid
    world_uid: EntityUid
    kind: OperationKind
    preparation_fingerprint: RevisionHex
    fence: Annotated[StrictInt, Field(ge=1)]


class StagingReservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    artifact_id: EntityUid
    lease: OperationLeaseRef
    ref: ArtifactRef
