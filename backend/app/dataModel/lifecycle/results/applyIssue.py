from enum import StrEnum
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class LifecycleApplyCode(StrEnum):
    CHANGE_PAYLOAD_CONFLICT = "change_payload_conflict"
    BEFORE_STATE_MISMATCH = "before_state_mismatch"
    EVIDENCE_MISMATCH = "evidence_mismatch"


class LifecycleApplyIssue(FieldPathError[LifecycleApplyCode]):
    pass
