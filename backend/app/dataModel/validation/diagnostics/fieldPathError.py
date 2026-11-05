"""Generic typed field issue and reference issue records.

Plan: ``.cursor/plans/error-contracts-1.md`` §3.9 C0-1/C0-2. Only named
concrete subclasses (``class XTypeError(FieldPathError[XCode])``) declared
in the owning domain ``dataModel`` are constructible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, ModelWrapValidatorHandler, StrictStr, model_validator

from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath


class ReferenceIssueReason(StrEnum):
    UNKNOWN_TEMPLATE = "unknown_template"
    OWNER_UNAVAILABLE = "owner_pack_unavailable"
    KIND_MISMATCH = "library_kind_mismatch"
    MISSING_DEPENDENCY = "missing_dependency"
    BODY_MISSING = "body_missing"
    DEFAULT_APPLIED = "default_applied"


@dataclass(frozen=True)
class ReferenceIssueContext:
    reason: ReferenceIssueReason
    domain: str
    world_uid: str | None = None
    requested_template_uid: str | None = None
    owner_pack_uid: str | None = None
    dependency_pack_uid: str | None = None
    consumer: str | None = None
    selected_default: str | None = None


CodeT = TypeVar("CodeT", bound=Enum)


class FieldPathError(BaseModel, Generic[CodeT]):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    code: CodeT
    path: ValidatedFieldPath
    message: StrictStr

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if _is_carrier(cls):
            raise TypeError("FieldPathError requires a named concrete domain subclass")
        return super().__new__(cls)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if _is_carrier(cls):
            return
        code = cls.model_fields["code"].annotation
        if not (isinstance(code, type) and issubclass(code, Enum)):
            raise TypeError(f"{cls.__qualname__} must bind CodeT to a concrete Enum, got {code!r}")

    @model_validator(mode="wrap")
    @classmethod
    def _validate_carrier(cls, value: Any, handler: ModelWrapValidatorHandler[Any]) -> Any:
        """Base/parameterized annotations admit concrete subclasses, revalidated by their own schema."""
        if not _is_carrier(cls):
            return handler(value)
        if not isinstance(value, FieldPathError):
            raise ValueError("FieldPathError carrier needs a named concrete domain subclass instance")
        kind = type(value)
        if _is_carrier(kind):
            raise ValueError("FieldPathError carrier needs a named concrete domain subclass instance")
        if not _admits(cls, kind):
            raise ValueError(f"{kind.__qualname__} does not match carrier {cls.__qualname__}")
        return kind.model_validate(value, strict=True)


def _is_carrier(kind: type[BaseModel]) -> bool:
    metadata = kind.__pydantic_generic_metadata__
    return kind is FieldPathError or metadata["origin"] is not None or bool(metadata["parameters"])


def _admits(carrier: type[BaseModel], kind: type[BaseModel]) -> bool:
    args = carrier.__pydantic_generic_metadata__["args"]
    if carrier is FieldPathError or all(arg is Any for arg in args):
        return True
    return issubclass(kind, carrier)
