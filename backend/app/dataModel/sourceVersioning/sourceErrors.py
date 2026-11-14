"""Single Source diagnostic value contract; spec §11.3, not a boundary implementation."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StrictInt, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class SourceOperation(StrEnum):
    ADMIT = "admit"
    READ = "read"
    ADMIT_GROUPS = "admit_groups"
    VERIFY_GROUPS = "verify_groups"
    SELECT = "select"
    VALIDATE_DESCRIPTOR = "validate_descriptor"
    FINALIZE_CAPTURE = "finalize_capture"
    READ_EXACT = "read_exact"
    PREPARE_MUTATION = "prepare_mutation"
    APPLY_MUTATION = "apply_mutation"
    ADOPT_CLOSURE = "adopt_closure"
    CHECK_COVERAGE = "check_coverage"


class SourceFieldCode(StrEnum):
    INVALID_SHAPE = "invalid_shape"
    INVALID_IDENTITY = "invalid_identity"
    NON_CANONICAL_PROOF = "non_canonical_proof"
    INVALID_SELECTION = "invalid_selection"
    GROUP_COUNT_MISMATCH = "group_count_mismatch"
    DUPLICATE_IDENTITY = "duplicate_identity"


class SourceFieldIssue(FieldPathError[SourceFieldCode]):
    """Concrete Source specialization of the shared field diagnostic."""


class SourceLogicCode(StrEnum):
    UNKNOWN_DESCRIPTOR = "unknown_descriptor"
    DESCRIPTOR_MISMATCH = "descriptor_mismatch"
    WRONG_WORLD = "wrong_world"
    CAPTURE_NOT_FINALIZED = "capture_not_finalized"
    CAPTURE_ID_CONFLICT = "capture_id_conflict"
    DEPENDENCY_NOT_CAPTURED = "dependency_not_captured"
    REVISION_CONFLICT = "revision_conflict"
    BODY_MAPPING_CONFLICT = "body_mapping_conflict"
    UNSUPPORTED_FORMAT = "unsupported_format"
    MISSING_BODY = "missing_body"
    CORRUPT_BODY = "corrupt_body"
    UNSEALED_BODY = "unsealed_body"
    INCOMPLETE_CLOSURE = "incomplete_closure"
    MISSING_HOLD = "missing_hold"
    INCOMPLETE_COLLECTION = "incomplete_collection"
    TOMBSTONE = "tombstone"
    PROOF_MISMATCH = "proof_mismatch"
    SELECTION_PROOF_MISMATCH = "selection_proof_mismatch"
    SELECTION_OUT_OF_RANGE = "selection_out_of_range"
    SELECTION_USAGE_MISMATCH = "selection_usage_mismatch"
    CLOSURE_MISMATCH = "closure_mismatch"


class SourceLogicIssue(SourceValue, frozen=True):
    code: SourceLogicCode
    group_index: Annotated[StrictInt, Field(ge=0)] | None
    use_index: Annotated[StrictInt, Field(ge=0)] | None
    source: SourceVersionRef | SourceCollectionVersionRef | None
    artifact: ArtifactRef | None


class SourceFailure(SourceValue, frozen=True):
    operation: SourceOperation
    field_issues: tuple[SourceFieldIssue, ...]
    logic_issues: tuple[SourceLogicIssue, ...]

    @model_validator(mode="after")
    def nonempty_failure(self) -> Self:
        if not self.field_issues and not self.logic_issues:
            raise ValueError("SourceFailure requires at least one issue")
        return self
