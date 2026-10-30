"""Reported artifact storage facts; this module never deletes content."""

from enum import StrEnum
from typing import Self
from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class ArtifactStorageEventKind(StrEnum):
    SEALED = "sealed"
    GC_DELETED = "gc_deleted"


class GcReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    deleted: tuple[ArtifactRef, ...]
    retained: tuple[ArtifactRef, ...]
    failed: tuple[FieldPathError, ...]

    @model_validator(mode="after")
    def disjoint_results(self) -> Self:
        if len(set(self.deleted)) != len(self.deleted) or len(set(self.retained)) != len(self.retained):
            raise ValueError("duplicate artifact in GC report")
        if set(self.deleted).intersection(self.retained):
            raise ValueError("deleted artifacts cannot also be retained")
        return self
