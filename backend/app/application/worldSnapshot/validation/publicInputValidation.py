"""Presentation of already classified structural facts; no input revalidation."""
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core.core_schema import ErrorType
from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.resolution.wireIssues import field_issue
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.patch.validation.admissionReasons import PatchSetStructuralFailure
from app.dataModel.patch.validation.structuralErrorKind import PatchSetStructuralErrorKind
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class SnapshotPublicInputValidation:
    @staticmethod
    def map_structural(fact: PatchSetStructuralFailure, *, model: type[BaseModel]
                       ) -> tuple[JsonFieldError | WireShapeIssue, ...]:
        fact = PatchSetStructuralFailure.model_validate(fact, strict=True)
        is_enum = fact.error_type is PatchSetStructuralErrorKind.ENUM
        try:
            pydantic_type = None if is_enum else TypeAdapter[ErrorType](ErrorType).validate_python(
                fact.error_type.value, strict=True)
        except ValidationError as error:
            raise PublicationInfrastructureError("unsupported structural presentation type") from error
        issue = field_issue(ResolveContext(collect_only=True), model, fact.loc,
            "unknown wire value; " + fact.message if is_enum else fact.message,
            JsonValidationCode.UNKNOWN_ENUM if is_enum else JsonValidationCode.SCHEMA_VIOLATION,
            pydantic_type)
        if type(issue) not in (JsonFieldError, WireShapeIssue):
            raise PublicationInfrastructureError("unexpected structural diagnostic output")
        assert isinstance(issue, (JsonFieldError, WireShapeIssue))
        return (issue,)
