"""Normalized world wire → REF-W lookup tables."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.jsonValidation.index.refKinds import RefKind


@dataclass(frozen=True)
class WorldRegistryIndex:
    """Import-time vocabulary index built after ``facade`` normalize."""

    materials: frozenset[str] | None = None
    liquids: frozenset[str] | None = None
    terrains: frozenset[str] | None = None
    climate_zones: frozenset[str] | None = None
    economic_tiers: frozenset[str] | None = None
    connection_types: frozenset[str] | None = None
    resources: frozenset[str] | None = None
    crops: frozenset[str] | None = None
    livestock: frozenset[str] | None = None

    def keys_for(self, ref: RefKind) -> frozenset[str] | None:
        return {
            RefKind.MATERIAL: self.materials,
            RefKind.LIQUID: self.liquids,
            RefKind.TERRAIN: self.terrains,
            RefKind.CLIMATE: self.climate_zones,
            RefKind.ECON_TIER: self.economic_tiers,
            RefKind.CONN: self.connection_types,
            RefKind.RESOURCE: self.resources,
            RefKind.CROP: self.crops,
            RefKind.LIVESTOCK: self.livestock,
        }.get(ref)
