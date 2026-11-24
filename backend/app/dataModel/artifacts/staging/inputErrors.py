"""Artifact-owned field diagnostics; shared structural issues are reused."""

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class ArtifactInputIssueCode(StrEnum):
    CONTENT_NOT_IMMUTABLE = "CONTENT_NOT_IMMUTABLE"
    CONTENT_TYPE_MISMATCH = "CONTENT_TYPE_MISMATCH"
    FORMAT_BINDING_MISMATCH = "FORMAT_BINDING_MISMATCH"
    DESCRIPTOR_MISMATCH = "DESCRIPTOR_MISMATCH"


class ArtifactInputIssue(FieldPathError[ArtifactInputIssueCode]):
    """A diagnostic for a declared artifact input field."""


class ArtifactInputError(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    issues: tuple[JsonFieldError | WireShapeIssue | ArtifactInputIssue, ...] = Field(min_length=1)
