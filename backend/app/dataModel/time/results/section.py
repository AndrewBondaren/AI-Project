from enum import StrEnum

from pydantic import Field

from app.dataModel.time.values.point import TimeRecord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class TimeSectionIssueCode(StrEnum):
    OPERATION_MISMATCH = "time.section.operation_mismatch"
    PUBLICATION_MISMATCH = "time.section.publication_mismatch"
    INVALID_KEY = "time.section.invalid_key"
    UNSUPPORTED_VERSION = "time.section.unsupported_version"
    DEPENDENCIES_FORBIDDEN = "time.section.dependencies_forbidden"


class TimeSectionFieldIssue(FieldPathError[TimeSectionIssueCode]):
    pass


class TimeSectionContextMismatch(TimeRecord):
    issues: tuple[TimeSectionFieldIssue, ...] = Field(min_length=1)
