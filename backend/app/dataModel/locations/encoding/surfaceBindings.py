"""Stable surface TLV registrations for app.dataModel.locations."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (52, GeographicSubtype, CanonicalTypeKind.ENUM),
)
