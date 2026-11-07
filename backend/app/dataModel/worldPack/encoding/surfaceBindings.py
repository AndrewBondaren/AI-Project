"""Stable surface TLV registrations for app.dataModel.worldPack."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (198, ParentLightRefinePolicy, CanonicalTypeKind.RECORD),
)
