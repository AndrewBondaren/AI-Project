"""A diagnostic fact and its declared disposition, with no logging behavior."""

from enum import StrEnum
from typing import Annotated, Any, Generic, NewType, ParamSpec, TypeAliasType, TypeVarTuple, get_args, get_origin
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


def _closed_argument(arg: object, bound: tuple[object, ...] = (),
                     expanding: tuple[TypeAliasType, ...] = ()) -> bool:
    if arg is Any:
        return False
    if isinstance(arg, (TypeVar, TypeVarTuple, ParamSpec)):
        return arg in bound
    origin = get_origin(arg)
    args = get_args(arg)
    alias = arg if isinstance(arg, TypeAliasType) else origin
    if isinstance(alias, TypeAliasType):
        if alias in expanding or len(args) != len(alias.__type_params__):
            return False
        # Check actual arguments before considering the alias parameters bound.
        return (all(_closed_argument(a, bound, expanding) for a in args)
                and _closed_argument(alias.__value__, alias.__type_params__, (*expanding, alias)))
    if isinstance(arg, NewType):
        return _closed_argument(arg.__supertype__, bound, expanding)
    if origin is Annotated:
        return _closed_argument(args[0], bound, expanding)
    if isinstance(arg, list):  # get_args(Callable[[A, B], R]) returns ([A, B], R).
        args = tuple(arg)
    elif isinstance(arg, type) and issubclass(arg, BaseModel):
        metadata = arg.__pydantic_generic_metadata__
        if metadata["parameters"]:
            return False
        args = metadata["args"]
    return all(_closed_argument(a, bound, expanding) for a in args)


def admits_diagnostic_type(kind: type) -> bool:
    if kind is PlanDiagnostic:
        return True
    if not issubclass(kind, PlanDiagnostic):
        return False
    metadata = kind.__pydantic_generic_metadata__
    fact = kind.model_fields["issue"].annotation
    return (metadata["origin"] is None and not metadata["parameters"]
            and isinstance(fact, type) and issubclass(fact, BaseModel) and fact is not BaseModel
            and _closed_argument(fact)
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
