"""A diagnostic fact and its declared disposition, with no logging behavior."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PlanDiagnosticDisposition(StrEnum):
    ERROR = "error"
    FALLBACK = "fallback"
    NOTICE = "notice"


class PlanDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    issue: FieldPathError
    disposition: PlanDiagnosticDisposition
