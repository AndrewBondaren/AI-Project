"""Stable surface TLV registrations for app.dataModel.fields."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.fields.validatedFieldPath import (
    FieldSegment,
    IndexSegment,
    KeySegment,
    ModelIdentity,
    ValidatedFieldPath,
    VariantSegment,
)


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (303, ValidatedFieldPath, CanonicalTypeKind.RECORD),
    (304, ModelIdentity, CanonicalTypeKind.RECORD),
    (305, FieldSegment, CanonicalTypeKind.RECORD),
    (306, VariantSegment, CanonicalTypeKind.RECORD),
    (307, IndexSegment, CanonicalTypeKind.RECORD),
    (308, KeySegment, CanonicalTypeKind.RECORD),
)
