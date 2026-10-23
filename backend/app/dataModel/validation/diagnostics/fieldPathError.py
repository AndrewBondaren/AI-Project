"""Pure issue records moved from application.jsonValidation.types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext


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


@dataclass(frozen=True)
class FieldPathError:
    path: tuple[str | int, ...]
    message: str
    schema_id: str | None = None
    code: str | None = None
    reference: ReferenceIssueContext | None = None
    runtime_context: RuntimeIssueContext[StrEnum, StrEnum] | None = None
