"""Generic typed field issue and reference issue records.

Plan: ``.cursor/plans/error-contracts-1.md`` §3.9 C0-1/C0-2. Only named
concrete subclasses (``class XTypeError(FieldPathError[XCode])``) declared
in the owning domain ``dataModel`` are constructible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, StrictStr

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

    def model_post_init(self, context: Any, /) -> None:
        metadata = type(self).__pydantic_generic_metadata__
        if type(self) is FieldPathError or metadata["origin"] is not None or metadata["parameters"]:
            raise TypeError("FieldPathError requires a named concrete domain subclass")
