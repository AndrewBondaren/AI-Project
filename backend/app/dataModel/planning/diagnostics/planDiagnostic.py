"""A diagnostic fact and its declared disposition, with no logging behavior."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PlanDiagnosticDisposition(StrEnum):
    ERROR = "error"
    FALLBACK = "fallback"
    NOTICE = "notice"


class PlanDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    issue: SerializeAsAny[FieldPathError[Any]]
    disposition: PlanDiagnosticDisposition
