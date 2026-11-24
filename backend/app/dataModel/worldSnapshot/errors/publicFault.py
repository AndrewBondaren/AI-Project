"""Non-persistent Snapshot boundary faults; admission has no claimed identity."""
from enum import StrEnum
from typing import Annotated, Self
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, GetPydanticSchema, model_validator
from pydantic_core import CoreSchema, core_schema
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.validation.admissionReasons import (
    PatchSetCompatibilityIssue, PatchSetRequestVersionUnsupported, PatchSetSectionKeyUnknown,
    PatchSetSectionModelMismatch, PatchSetSectionVersionUnsupported,
)
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class SnapshotPublicOperation(StrEnum):
    APPLY = "apply"
    READ_SNAPSHOT = "read_snapshot"
    READ_PUBLICATION = "read_publication"


class SnapshotPublicFailureKind(StrEnum):
    INVALID_INPUT = "invalid_input"
    ADMISSION_REFUSED = "admission_refused"
    BUSY = "busy"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    OUTCOME_UNKNOWN = "outcome_unknown"


SnapshotInputIssue = (JsonFieldError | WireShapeIssue | PatchSetInvariantViolation
    | Annotated[PatchSetCompatibilityIssue, Field(discriminator="code")])
SNAPSHOT_INPUT_ISSUE_TYPES = (JsonFieldError, WireShapeIssue, PatchSetInvariantViolation,
    PatchSetRequestVersionUnsupported, PatchSetSectionKeyUnknown,
    PatchSetSectionModelMismatch, PatchSetSectionVersionUnsupported)


def _exact_instances(value: object) -> object:
    if isinstance(value, (tuple, list)):
        if any(isinstance(issue, BaseModel) and type(issue) not in SNAPSHOT_INPUT_ISSUE_TYPES for issue in value):
            raise ValueError("fault contains an undeclared diagnostic class")
    return value


def _input_issue_schema(source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
    schema = handler(source)
    return core_schema.json_or_python_schema(json_schema=schema,
        python_schema=core_schema.no_info_before_validator_function(_exact_instances, schema))


class SnapshotPublicFault(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    operation: SnapshotPublicOperation
    kind: SnapshotPublicFailureKind
    operation_id: EntityUid | None
    request_fingerprint: RevisionHex | None
    input_issues: Annotated[tuple[SnapshotInputIssue, ...], GetPydanticSchema(_input_issue_schema)]

    @model_validator(mode="after")
    def coherent_fault(self) -> Self:
        if (self.operation_id is None) != (self.request_fingerprint is None):
            raise ValueError("fault binding must be complete or absent")
        if any(type(issue) not in SNAPSHOT_INPUT_ISSUE_TYPES for issue in self.input_issues):
            raise ValueError("fault contains an undeclared diagnostic class")
        if self.kind in (SnapshotPublicFailureKind.INVALID_INPUT, SnapshotPublicFailureKind.ADMISSION_REFUSED):
            if not self.input_issues or self.operation_id is not None:
                raise ValueError("admission fault requires diagnostics and no binding")
            relations = any(type(issue) not in (JsonFieldError, WireShapeIssue) for issue in self.input_issues)
            if relations != (self.kind is SnapshotPublicFailureKind.ADMISSION_REFUSED):
                raise ValueError("fault kind must match shape or relation diagnostics")
            if relations and self.operation is not SnapshotPublicOperation.APPLY:
                raise ValueError("admission relations belong to apply")
        elif self.input_issues:
            raise ValueError("execution faults cannot carry admission diagnostics")
        if self.operation is not SnapshotPublicOperation.APPLY and self.operation_id is not None:
            raise ValueError("read fault cannot have operation binding")
        if self.kind in (SnapshotPublicFailureKind.BUSY, SnapshotPublicFailureKind.OUTCOME_UNKNOWN):
            if self.operation is not SnapshotPublicOperation.APPLY or self.operation_id is None:
                raise ValueError("busy and unknown require apply binding")
        return self
