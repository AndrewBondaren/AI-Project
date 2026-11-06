"""Reported artifact storage facts; this module never deletes content."""

from enum import StrEnum
from typing import Self
from pydantic import BaseModel, ConfigDict, StrictStr, StrictInt, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid


class ArtifactStorageEventKind(StrEnum):
    SEALED = "sealed"
    GC_DELETED = "gc_deleted"


class GcFailureCode(StrEnum):
    IO_ERROR = "io_error"
    VALUE_ERROR = "value_error"


class GcFailureStage(StrEnum):
    VALIDATE = "validate"
    GUARD_ENTER = "guard_enter"
    CATALOG_READ = "catalog_read"
    HOLDERS_READ = "holders_read"
    DELETE = "delete"
    MARK_DELETED = "mark_deleted"
    GUARD_EXIT = "guard_exit"


class ArtifactGcFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    failure_id: EntityUid
    ref: ArtifactRef
    stage: GcFailureStage
    code: GcFailureCode
    exception_type: StrictStr
    message: StrictStr
    errno: StrictInt | None
    winerror: StrictInt | None

    @model_validator(mode="after")
    def value_error_has_no_os_codes(self) -> Self:
        if self.code is GcFailureCode.VALUE_ERROR and (self.errno is not None or self.winerror is not None):
            raise ValueError("ValueError cannot carry OS error codes")
        return self


class GcReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    deleted: tuple[ArtifactRef, ...]
    retained: tuple[ArtifactRef, ...]
    failed: tuple[ArtifactGcFailure, ...]

    @model_validator(mode="after")
    def disjoint_results(self) -> Self:
        refs = (*self.deleted, *self.retained, *(failure.ref for failure in self.failed))
        if len(set(refs)) != len(refs):
            raise ValueError("duplicate artifact in GC report")
        if set(self.deleted).intersection(self.retained):
            raise ValueError("deleted artifacts cannot also be retained")
        return self
