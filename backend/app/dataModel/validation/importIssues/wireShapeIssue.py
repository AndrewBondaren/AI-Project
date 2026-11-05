"""F09 issue where no POJO or declared field exists (raw rows, removed or rejected sections)."""

from typing import Self

from pydantic import BaseModel, ConfigDict, StrictStr, model_validator
from pydantic_core.core_schema import ErrorType

from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation


class WireShapeIssue(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    code: JsonValidationCode
    location: WireLocation
    message: StrictStr
    pydantic_type: ErrorType | None = None

    @model_validator(mode="after")
    def _pydantic_type_only_for_schema_violation(self) -> Self:
        if (self.code is JsonValidationCode.SCHEMA_VIOLATION) != (self.pydantic_type is not None):
            raise ValueError("pydantic_type is required exactly for SCHEMA_VIOLATION")
        return self
