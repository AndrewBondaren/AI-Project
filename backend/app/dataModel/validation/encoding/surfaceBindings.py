"""Stable surface TLV registrations for app.dataModel.validation."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.validation.diagnostics.fieldPathError import (
    FieldPathError,
    ReferenceIssueContext,
    ReferenceIssueReason,
)
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (28, ResolutionMode, CanonicalTypeKind.ENUM),
    (106, FieldPathError, CanonicalTypeKind.RECORD),
    (107, ReferenceIssueContext, CanonicalTypeKind.RECORD),
    (108, ReferenceIssueReason, CanonicalTypeKind.ENUM),
    (109, RuntimeIssueContext, CanonicalTypeKind.RECORD),
)
