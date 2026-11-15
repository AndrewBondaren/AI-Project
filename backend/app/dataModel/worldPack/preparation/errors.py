"""Diagnostics of Pack preparation, separate from storage and read refusals."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.artifacts.references import ArtifactRef

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
    RESOURCE_LIMIT = "resource_limit"


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
    RETENTION_LIMIT_EXCEEDED = "retention_limit_exceeded"


class PackPreparationIssue(FieldPathError[PackPreparationIssueCode]):
    pass


PackPreparationLeafDiagnostic = JsonFieldError | WireShapeIssue | PackPreparationIssue


class PackPreparationArtifactIssue(BaseModel):
    """Locate an owning payload diagnostic without rewriting its field path."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    artifact: ArtifactRef
    issue: PackPreparationLeafDiagnostic


class PackRetentionResource(StrEnum):
    READ_BYTES = "read_bytes"
    ARTIFACTS = "artifacts"


class PackPreparationRetentionLimitIssue(BaseModel):
    """An admission reservation refused before the attempted action starts."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    code: Literal[PackPreparationIssueCode.RETENTION_LIMIT_EXCEEDED]
    resource: PackRetentionResource
    limit: Annotated[StrictInt, Field(gt=0)]
    consumed: Annotated[StrictInt, Field(ge=0)]
    requested: Annotated[StrictInt, Field(gt=0)]
    artifact: ArtifactRef

    @model_validator(mode="after")
    def reservation(self) -> Self:
        if self.consumed > self.limit or self.consumed + self.requested <= self.limit:
            raise ValueError("reservation must exceed the remaining budget")
        expected = self.artifact.nbytes if self.resource is PackRetentionResource.READ_BYTES else 1
        if self.requested != expected:
            raise ValueError("reservation must match the attempted artifact action")
        return self


PackPreparationDiagnostic = (
    PackPreparationLeafDiagnostic | PackPreparationArtifactIssue | PackPreparationRetentionLimitIssue
)


def is_structural_preparation_issue(issue: PackPreparationDiagnostic) -> bool:
    leaf = issue.issue if isinstance(issue, PackPreparationArtifactIssue) else issue
    return isinstance(leaf, (JsonFieldError, WireShapeIssue))


class PackPreparationError(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    reason: PackPreparationFailureReason
    issues: tuple[PackPreparationDiagnostic, ...]

    @model_validator(mode="after")
    def diagnostic_shape(self) -> Self:
        if not self.issues and self.reason is not PackPreparationFailureReason.MANIFEST_OVERSIZE:
            raise ValueError("preparation refusal requires diagnostics")
        limits = tuple(i for i, issue in enumerate(self.issues)
                       if isinstance(issue, PackPreparationRetentionLimitIssue))
        if self.reason is PackPreparationFailureReason.RESOURCE_LIMIT:
            if limits != (len(self.issues) - 1,):
                raise ValueError("resource interruption requires exactly one final limit diagnostic")
        elif limits:
            raise ValueError("limit diagnostics require resource_limit")
        if any(is_structural_preparation_issue(issue) for issue in self.issues):
            if self.reason not in (PackPreparationFailureReason.INVALID_INPUT,
                                   PackPreparationFailureReason.RESOURCE_LIMIT):
                raise ValueError("structural diagnostics require invalid_input")
        validate_immutable(self)
        return self
