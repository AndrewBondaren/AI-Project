"""RegistryKey[R] — N1-W identity branded string, not a bare str."""

from __future__ import annotations

import unittest
from typing import get_origin

from app.dataModel.annotationPolicy import (
    DefaultOnWire,
    StrictOnWire,
    WireFieldPolicy,
    field_policy,
    unwrap_wire_type,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.registryKey import RegistryKey, registry_key_target
from app.dataModel.settlement.settlement.settlementSizeEntry import SettlementSizeEntry
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    SettlementSizeKey,
    WorldSettlementSizeRegistry,
)
from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import (
    EconomyTierKey,
    WorldEconomyTierRegistry,
)
from app.dataModel.settlement.district.placementCondition import PlacementCondition
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey, WorldTerrainRegistry


class TestRegistryKey(unittest.TestCase):
    def test_wire_str_coerces_to_branded_key(self) -> None:
        entry = SettlementSizeEntry(system_size="small")
        self.assertIsInstance(entry.system_size, RegistryKey)
        self.assertEqual(entry.system_size, "small")
        self.assertEqual(entry.model_dump(mode="json")["system_size"], "small")

    def test_empty_key_rejected(self) -> None:
        with self.assertRaises(Exception):
            SettlementSizeEntry(system_size="")

    def test_canonical_keys_are_branded(self) -> None:
        medium = WorldSettlementSizeRegistry.default_system_size()
        self.assertIsInstance(medium, RegistryKey)
        self.assertEqual(
            medium,
            WorldSettlementSizeRegistry.canonical_defaults().root[1].system_size,
        )

    def test_annotation_points_at_size_registry(self) -> None:
        annotation = SettlementSizeEntry.model_fields["system_size"].annotation
        self.assertEqual(field_policy(annotation), WireFieldPolicy.STRICT_ON_WIRE)
        self.assertIs(
            registry_key_target(annotation),
            WorldSettlementSizeRegistry,
        )
        inner = unwrap_wire_type(annotation)
        self.assertIs(get_origin(inner), RegistryKey)
        self.assertIs(registry_key_target(SettlementSizeKey), WorldSettlementSizeRegistry)
        self.assertIs(
            registry_key_target(DefaultOnWire[SettlementSizeKey | None]),
            WorldSettlementSizeRegistry,
        )

    def test_size_key_is_not_location_type_key(self) -> None:
        loc_ann = StrictOnWire[RegistryKey[WorldLocationTypeRegistry]]
        self.assertIs(registry_key_target(loc_ann), WorldLocationTypeRegistry)
        self.assertIsNot(
            registry_key_target(loc_ann),
            registry_key_target(SettlementSizeEntry.model_fields["system_size"].annotation),
        )

    def test_economy_and_terrain_identity_are_branded(self) -> None:
        tier = WorldEconomyTierRegistry.canonical_defaults().root[2]
        self.assertIsInstance(tier.system_tier, RegistryKey)
        self.assertEqual(tier.system_tier, "standard")
        terrain = WorldTerrainRegistry.canonical_defaults().entry_for("liquid_body")
        assert terrain is not None
        self.assertIsInstance(terrain.system_terrain, RegistryKey)
        self.assertEqual(terrain.system_terrain, "liquid_body")

    def test_economy_and_terrain_annotations_point_at_registries(self) -> None:
        self.assertIs(
            registry_key_target(EconomyTierEntry.model_fields["system_tier"].annotation),
            WorldEconomyTierRegistry,
        )
        self.assertIs(
            registry_key_target(TerrainRegistryEntry.model_fields["system_terrain"].annotation),
            WorldTerrainRegistry,
        )
        self.assertIs(registry_key_target(EconomyTierKey), WorldEconomyTierRegistry)
        self.assertIs(registry_key_target(TerrainKey), WorldTerrainRegistry)
        self.assertIsNot(
            registry_key_target(EconomyTierKey),
            registry_key_target(TerrainKey),
        )

    def test_empty_economy_and_terrain_keys_rejected(self) -> None:
        with self.assertRaises(Exception):
            EconomyTierEntry(system_tier="", display_tier="x", base_value=0)
        with self.assertRaises(Exception):
            TerrainRegistryEntry(system_terrain="", terrain_category="solid")

    def test_list_of_keys_peels_to_registry(self) -> None:
        self.assertIs(
            registry_key_target(DefaultOnWire[list[TerrainKey] | None]),
            WorldTerrainRegistry,
        )
        self.assertIs(
            registry_key_target(
                PlacementCondition.model_fields["terrain_types"].annotation,
            ),
            WorldTerrainRegistry,
        )
        self.assertIs(
            registry_key_target(PlacementCondition.model_fields["tier"].annotation),
            WorldEconomyTierRegistry,
        )
        self.assertIs(
            registry_key_target(PlacementCondition.model_fields["size"].annotation),
            WorldSettlementSizeRegistry,
        )
        self.assertIsNone(
            registry_key_target(PlacementCondition.model_fields["district_type"].annotation),
        )

    def test_city_economy_tier_refs_are_branded(self) -> None:
        from app.dataModel.locations.namedLocation.bundleNamedLocation import (
            BundleNamedLocation,
        )
        from app.dataModel.settlement.settlement.settlementSkeleton import (
            SettlementSkeleton,
        )
        from app.dataModel.shared.ranges import EconomicTierRange
        from app.dataModel.structure.building.buildingLayoutTemplate import (
            BuildingLayoutTemplate,
        )

        skeleton = SettlementSkeleton(economic_tier="standard")
        self.assertIsInstance(skeleton.economic_tier, RegistryKey)
        self.assertEqual(skeleton.economic_tier, "standard")

        loc = BundleNamedLocation(
            location_uid="loc-1",
            display_name="X",
            system_location_type="settlement",
            system_economic_tier="quality",
        )
        self.assertIsInstance(loc.system_economic_tier, RegistryKey)
        self.assertEqual(loc.system_economic_tier, "quality")

        bounds = EconomicTierRange(min="basic", max="premium")
        self.assertIsInstance(bounds.min, RegistryKey)
        self.assertIsInstance(bounds.max, RegistryKey)
        self.assertEqual((bounds.min, bounds.max), ("basic", "premium"))

        self.assertIs(
            registry_key_target(SettlementSkeleton.model_fields["economic_tier"].annotation),
            WorldEconomyTierRegistry,
        )
        self.assertIs(
            registry_key_target(
                BundleNamedLocation.model_fields["system_economic_tier"].annotation,
            ),
            WorldEconomyTierRegistry,
        )
        self.assertIs(
            registry_key_target(EconomicTierRange.model_fields["min"].annotation),
            WorldEconomyTierRegistry,
        )
        self.assertIs(
            registry_key_target(
                BuildingLayoutTemplate.model_fields["economic_tier"].annotation,
            ),
            WorldEconomyTierRegistry,
        )
        with self.assertRaises(Exception):
            SettlementSkeleton(economic_tier="")
        with self.assertRaises(Exception):
            EconomicTierRange(min="", max="standard")

    def test_skeleton_material_density_and_nl_overlay_map(self) -> None:
        from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
        from app.dataModel.materials.worldMaterialRegistry import (
            MaterialKey,
            WorldMaterialRegistry,
        )
        from app.dataModel.settlement.enums.districtDensity import DistrictDensity
        from app.dataModel.settlement.settlement.settlementSkeleton import (
            SettlementSkeleton,
        )

        stone = WorldMaterialRegistry.canonical_defaults().entry_for("stone")
        assert stone is not None
        self.assertIsInstance(stone.system_material, RegistryKey)
        self.assertIs(
            registry_key_target(
                MaterialRegistryEntry.model_fields["system_material"].annotation,
            ),
            WorldMaterialRegistry,
        )
        self.assertIs(registry_key_target(MaterialKey), WorldMaterialRegistry)

        skeleton = SettlementSkeleton(
            dominant_material="stone",
            settlement_density="medium",
        )
        self.assertIsInstance(skeleton.dominant_material, RegistryKey)
        self.assertEqual(skeleton.dominant_material, "stone")
        self.assertIs(skeleton.settlement_density, DistrictDensity.MEDIUM)
        self.assertIs(
            registry_key_target(
                SettlementSkeleton.model_fields["dominant_material"].annotation,
            ),
            WorldMaterialRegistry,
        )
        with self.assertRaises(Exception):
            SettlementSkeleton(dominant_material="")
        with self.assertRaises(Exception):
            SettlementSkeleton(settlement_density="huge")

        overlay = set(SettlementSkeleton.NAMED_LOCATION_OVERLAY_FIELDS)
        aliases = set(SettlementSkeleton.NAMED_LOCATION_FIELD_ALIASES)
        fields = set(SettlementSkeleton.model_fields)
        self.assertTrue(overlay <= fields)
        self.assertTrue(aliases <= fields)
        self.assertEqual(
            SettlementSkeleton.NAMED_LOCATION_FIELD_ALIASES["economic_tier"],
            "system_economic_tier",
        )


if __name__ == "__main__":
    unittest.main()
