"""Normalized world wire → REF-W lookup tables."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.jsonValidation.index.refKinds import RefKind


@dataclass(frozen=True)
class WorldRegistryIndex:
    """Import-time vocabulary index built after ``facade`` normalize."""

    registry_vocabularies: dict[type, frozenset[str]] = field(default_factory=dict)
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

    def keys_for_registry(self, registry: type) -> frozenset[str] | None:
        """RegistryKey's nominal target → the existing REF-W vocabulary."""
        if registry in self.registry_vocabularies:
            return self.registry_vocabularies[registry]
        from app.dataModel.economy.economyTier.worldEconomyTierRegistry import WorldEconomyTierRegistry
        from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
        from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
        from app.dataModel import WorldClimateZoneRegistry
        from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import WorldConnectionTypeRegistry
        from app.dataModel.resources.worldResourceTypeRegistry import WorldResourceTypeRegistry
        from app.dataModel.flora.worldCropsRegistry import WorldCropsRegistry
        from app.dataModel.livestock.worldLivestockRegistry import WorldLivestockRegistry
        ref = {
            WorldEconomyTierRegistry: RefKind.ECON_TIER,
            WorldMaterialRegistry: RefKind.MATERIAL,
            WorldTerrainRegistry: RefKind.TERRAIN,
            WorldClimateZoneRegistry: RefKind.CLIMATE,
            WorldConnectionTypeRegistry: RefKind.CONN,
            WorldResourceTypeRegistry: RefKind.RESOURCE,
            WorldCropsRegistry: RefKind.CROP,
            WorldLivestockRegistry: RefKind.LIVESTOCK,
        }.get(registry)
        return self.keys_for(ref) if ref is not None else None
