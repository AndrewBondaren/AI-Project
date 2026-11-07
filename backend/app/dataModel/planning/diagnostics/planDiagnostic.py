"""A diagnostic fact and its declared disposition, with no logging behavior."""

from enum import StrEnum
from typing import Annotated, Any, Generic
from typing_extensions import TypeVar

from pydantic import BaseModel, ConfigDict, PlainValidator, SerializeAsAny

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PlanDiagnosticDisposition(StrEnum):
    ERROR = "error"
    FALLBACK = "fallback"
    NOTICE = "notice"


IssueT = TypeVar("IssueT", bound=BaseModel, default=FieldPathError[Any])


class PlanDiagnostic(BaseModel, Generic[IssueT]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    issue: SerializeAsAny[IssueT]
    disposition: PlanDiagnosticDisposition


def admits_diagnostic_type(kind: type) -> bool:
    if kind is PlanDiagnostic:
        return True
    if not issubclass(kind, PlanDiagnostic):
        return False
    metadata = kind.__pydantic_generic_metadata__
    fact = kind.model_fields["issue"].annotation
    return (metadata["origin"] is None and not metadata["parameters"]
            and isinstance(fact, type) and issubclass(fact, BaseModel) and fact is not BaseModel
            and not fact.__pydantic_generic_metadata__["parameters"]
            and Any not in fact.__pydantic_generic_metadata__["args"]
            and fact.model_config.get("revalidate_instances") == "always"
            and kind.model_config.get("revalidate_instances") == "always")


def require_concrete_diagnostic(value: object) -> PlanDiagnostic[Any]:
    if not isinstance(value, PlanDiagnostic):
        raise ValueError("expected a reconstructed planning diagnostic")
    kind = type(value)
    issue = getattr(value, "issue", None)
    if not admits_diagnostic_type(kind):
        raise ValueError("expected a named diagnostic with a concrete issue type")
    if kind is PlanDiagnostic:
        if not isinstance(issue, FieldPathError):
            raise ValueError("field diagnostic requires a concrete field issue")
    elif type(issue) is not kind.model_fields["issue"].annotation:
        raise ValueError("diagnostic issue does not match its declared type")
    checked = kind.model_validate(value, strict=True)
    if type(checked) is not kind or type(checked.issue) is not type(issue):
        raise ValueError("planning diagnostic changed type during validation")
    return checked


DiagnosticCarrier = Annotated[
    SerializeAsAny[PlanDiagnostic[Any]], PlainValidator(require_concrete_diagnostic)
]
