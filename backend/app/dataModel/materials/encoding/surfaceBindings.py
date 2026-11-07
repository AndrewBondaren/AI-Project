"""Stable surface TLV registrations for app.dataModel.materials."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (42, WorldMaterialRegistry, CanonicalTypeKind.RECORD),
    (43, MaterialRegistryEntry, CanonicalTypeKind.RECORD),
    (44, MaterialCategory, CanonicalTypeKind.ENUM),
    (178, MaterialSubstrateKind, CanonicalTypeKind.ENUM),
)
