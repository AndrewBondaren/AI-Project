from enum import StrEnum

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class AdmissionIssueCode(StrEnum):
    INVALID_EXECUTION_ID = "invalid_execution_id"
    INVALID_MAX_PASSES = "invalid_max_passes"
    INVALID_TASK_TYPE = "invalid_task_type"
    INVALID_OPTIONS = "invalid_options"


class AdmissionFieldIssue(FieldPathError[AdmissionIssueCode]):
    pass
