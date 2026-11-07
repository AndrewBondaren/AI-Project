"""Stable surface TLV registrations for app.dataModel.regions."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.regions.regionState import (
    RegionState,
    RegionStateOverrides,
    RegionStateTransition,
    RegionTransitionCause,
)


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (179, RegionState, CanonicalTypeKind.RECORD),
    (180, RegionStateOverrides, CanonicalTypeKind.RECORD),
    (181, RegionStateTransition, CanonicalTypeKind.RECORD),
    (182, RegionTransitionCause, CanonicalTypeKind.ENUM),
)
