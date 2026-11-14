"""Diagnostics of Pack preparation, separate from storage and read refusals."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class PackPreparationFailureReason(StrEnum):
    INVALID_INPUT = "invalid_input"
    IDENTITY_CONFLICT = "identity_conflict"
    SOURCE_UNAVAILABLE = "source_unavailable"
    DEPENDENCY_MISMATCH = "dependency_mismatch"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    MANIFEST_OVERSIZE = "manifest_oversize"
    OPERATION_CLOSED = "operation_closed"


class PackPreparationIssueCode(StrEnum):
    DUPLICATE_ADDRESS = "duplicate_address"
    MISSING_PART = "missing_part"
    UNEXPECTED_PART = "unexpected_part"
    FORMAT_MISMATCH = "format_mismatch"
    ADDRESS_MISMATCH = "address_mismatch"
    SOURCE_PROOF_MISMATCH = "source_proof_mismatch"
    BASE_PUBLICATION_MISMATCH = "base_publication_mismatch"
    STATUS_MISMATCH = "status_mismatch"
    IDENTITY_MISMATCH = "identity_mismatch"
    HOLD_MISSING = "hold_missing"
    ARTIFACT_UNSEALED = "artifact_unsealed"
    MANIFEST_LIMIT_EXCEEDED = "manifest_limit_exceeded"
    SOURCE_HOLD_MISSING = "source_hold_missing"
    OPERATION_CLOSED = "operation_closed"
    METADATA_PROOF_MISSING = "metadata_proof_missing"
    OUT_OF_SCOPE_CHANGE = "out_of_scope_change"
    METADATA_GROUP_MISMATCH = "metadata_group_mismatch"
    METADATA_ATTRIBUTION_UNAVAILABLE = "metadata_attribution_unavailable"
    METADATA_INPUT_MISMATCH = "metadata_input_mismatch"
    METADATA_BASIS_MISMATCH = "metadata_basis_mismatch"


class PackPreparationIssue(FieldPathError[PackPreparationIssueCode]):
    pass


PackPreparationDiagnostic = JsonFieldError | WireShapeIssue | PackPreparationIssue


class PackPreparationError(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    reason: PackPreparationFailureReason
    issues: tuple[PackPreparationDiagnostic, ...]

    @model_validator(mode="after")
    def diagnostic_shape(self) -> Self:
        if not self.issues and self.reason is not PackPreparationFailureReason.MANIFEST_OVERSIZE:
            raise ValueError("preparation refusal requires diagnostics")
        if any(isinstance(issue, (JsonFieldError, WireShapeIssue)) for issue in self.issues):
            if self.reason is not PackPreparationFailureReason.INVALID_INPUT:
                raise ValueError("structural diagnostics require invalid_input")
        validate_immutable(self)
        return self
