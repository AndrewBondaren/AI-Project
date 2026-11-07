"""Stable surface TLV registrations for app.dataModel.topology."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (53, WorldTopology, CanonicalTypeKind.RECORD),
    (54, WorldTopologyMode, CanonicalTypeKind.ENUM),
    (55, WorldBounds, CanonicalTypeKind.RECORD),
)
