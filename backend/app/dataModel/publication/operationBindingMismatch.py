"""Exact requested/stored immutable binding facts, never an operation mutation."""
from typing import Self
from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class OperationBindingMismatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    operation_id: EntityUid
    requested_kind: OperationKind
    requested_world_uid: EntityUid
    requested_preparation_fingerprint: RevisionHex
    requested_request_fingerprint: RevisionHex
    stored_kind: OperationKind
    stored_world_uid: EntityUid
    stored_preparation_fingerprint: RevisionHex
    stored_request_fingerprint: RevisionHex | None

    @model_validator(mode="after")
    def actual_mismatch(self) -> Self:
        if (self.requested_kind is self.stored_kind
                and self.requested_world_uid == self.stored_world_uid
                and self.requested_preparation_fingerprint == self.stored_preparation_fingerprint
                and (self.stored_request_fingerprint is None
                     or self.requested_request_fingerprint == self.stored_request_fingerprint)):
            raise ValueError("immutable bindings do not differ")
        return self
