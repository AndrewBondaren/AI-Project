"""F01 field error of a POJO validated by jsonValidation."""

from typing import Self

from pydantic import Field, StrictStr, model_validator
from pydantic_core.core_schema import ErrorType

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation, WirePart


class JsonFieldError(FieldPathError[JsonValidationCode]):
    """``path`` starts at the validated POJO; ``location`` places that POJO in the document.

    ``wire_path`` keeps the keys actually used in the input (alias choice), fixed
    while the POJO class is known; ``path`` keeps canonical field names.
    """

    location: WireLocation
    wire_path: tuple[WirePart, ...] = Field(min_length=1)
    schema_id: StrictStr | None = None
    pydantic_type: ErrorType | None = None

    @model_validator(mode="after")
    def _pydantic_type_only_for_schema_violation(self) -> Self:
        if (self.code is JsonValidationCode.SCHEMA_VIOLATION) != (self.pydantic_type is not None):
            raise ValueError("pydantic_type is required exactly for SCHEMA_VIOLATION")
        return self
