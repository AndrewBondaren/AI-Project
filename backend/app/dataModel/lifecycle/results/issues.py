from enum import StrEnum
from pydantic import BaseModel, ConfigDict, StrictStr
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class LifecycleFieldCode(StrEnum):
    UNKNOWN_FACT = "unknown_fact"
    REQUIRED_FACT_MISSING = "required_fact_missing"
    UNSUPPORTED_REASON = "unsupported_reason"
    INVALID_STATE = "invalid_state"
    REACTIVATION_RULE_UNSUPPORTED = "reactivation_rule_unsupported"


class LifecycleRelationCode(StrEnum):
    BASE_MISMATCH = "base_mismatch"
    IDENTITY_MISMATCH = "identity_mismatch"
    REASON_OPERATION_MISMATCH = "reason_operation_mismatch"
    ADMISSION_MISMATCH = "admission_mismatch"
    DUPLICATE_PARTICIPANT = "duplicate_participant"
    PARTICIPANT_OVERLAP = "participant_overlap"
    DUPLICATE_CHANGE_UID = "duplicate_change_uid"
    COVERAGE_MISSING = "coverage_missing"
    COVERAGE_EXTRA = "coverage_extra"
    COVERAGE_DUPLICATE = "coverage_duplicate"
    PATCH_OPERATION_MISMATCH = "patch_operation_mismatch"
    PATCH_SECTION_MISMATCH = "patch_section_mismatch"
    FINGERPRINT_CONFLICT = "fingerprint_conflict"
    SELF_DEPENDENCY = "self_dependency"


class LifecycleFieldIssue(FieldPathError[LifecycleFieldCode]):
    pass


class LifecycleRelationIssue(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    code: LifecycleRelationCode
    path: ValidatedFieldPath
    related_path: ValidatedFieldPath | None
    message: StrictStr


LifecycleIssue = LifecycleFieldIssue | LifecycleRelationIssue
