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

    def test_city_skeleton_resolved_tier_overrides_nl_and_keeps_size_brand(self) -> None:
        from app.application.worldData.generators.assemblers.citySkeleton import (
            city_skeleton_from_settlement,
        )
        from app.db.models.namedLocation import NamedLocation

        loc = NamedLocation(
            location_uid="loc-1",
            world_uid="w1",
            display_name="Hold",
            system_location_type="settlement",
            created_at="2026-01-01T00:00:00",
            system_city_size="small",
            system_economic_tier="poor",
            dominant_material="stone",
            system_location_mood="prosperous",
        )
        skeleton = city_skeleton_from_settlement(loc, economic_tier="quality")
        self.assertIsInstance(skeleton.economic_tier, RegistryKey)
        self.assertEqual(skeleton.economic_tier, "quality")
        self.assertIsNone(skeleton.dominant_material)
        self.assertIsInstance(skeleton.system_city_size, RegistryKey)
        self.assertEqual(skeleton.system_city_size, "small")
        self.assertEqual(skeleton.system_location_mood, "prosperous")
        cleared = city_skeleton_from_settlement(loc, economic_tier=None)
        self.assertIsNone(cleared.economic_tier)

    def test_drawing_key_is_layout_identity(self) -> None:
        from app.dataModel.settlement.district.districtTemplateEntry import (
            DistrictTemplateEntry,
        )
        from app.dataModel.settlement.district.requiredStructure import RequiredStructure
        from app.dataModel.structure.building.buildingLayoutTemplate import (
            BuildingLayoutTemplate,
            DrawingKey,
        )

        self.assertIs(registry_key_target(DrawingKey), BuildingLayoutTemplate)
        self.assertIs(
            registry_key_target(
                BuildingLayoutTemplate.model_fields["system_name"].annotation,
            ),
            BuildingLayoutTemplate,
        )
        self.assertIs(
            registry_key_target(
                RequiredStructure.model_fields["building_template"].annotation,
            ),
            BuildingLayoutTemplate,
        )
        layout = BuildingLayoutTemplate(
            system_name="tavern_1",
            structure_type="tavern",
            display_name="Inn",
        )
        self.assertIsInstance(layout.system_name, RegistryKey)
        pin = RequiredStructure(building_template="tavern_1")
        self.assertIsInstance(pin.building_template, RegistryKey)
        district = DistrictTemplateEntry(
            system_name="inn_row",
            display_name="Inns",
            district_type="commercial",
            plot_counts={"tavern_1": 3},
        )
        key = next(iter(district.plot_counts or {}))
        self.assertIsInstance(key, RegistryKey)
        self.assertEqual(district.plot_counts["tavern_1"], 3)
        aliased = DistrictTemplateEntry(
            system_name="inn_row",
            display_name="Inns",
            district_type="commercial",
            structure_counts={"tavern_1": 2},
        )
        self.assertEqual(aliased.plot_counts["tavern_1"], 2)
        with self.assertRaises(Exception):
            RequiredStructure(building_template="")

    def test_connection_type_identity_and_city_refs_are_branded(self) -> None:
        from app.dataModel.connections.connectionType.connectionTypeEntry import (
            ConnectionTypeEntry,
        )
        from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
            ConnectionTypeKey,
            WorldConnectionTypeRegistry,
        )
        from app.dataModel.locations.namedLocation.bundleNamedLocation import (
            BundleNamedLocation,
        )
        from app.dataModel.settlement.district.districtConnection import (
            DEFAULT_CONNECTION_TYPE,
            DistrictConnection,
        )
        from app.dataModel.settlement.district.districtTemplateEntry import (
            DistrictTemplateEntry,
        )
        from app.dataModel.settlement.district.districtTopologySlot import (
            DistrictTopologyEntry,
        )
        from app.dataModel.settlement.district.frontageTypeOrder import (
            FrontageTypeOrder,
        )
        from app.dataModel.settlement.enums.districtEntryRole import DistrictEntryRole
        from app.dataModel.settlement.settlement.settlementSkeleton import (
            SettlementSkeleton,
        )
        from app.dataModel.spatial.facing import Facing

        road = WorldConnectionTypeRegistry.canonical_engine().entry_for("road")
        assert road is not None
        self.assertIsInstance(road.system_connection_type, RegistryKey)
        self.assertEqual(road.system_connection_type, "road")
        self.assertIsInstance(
            WorldConnectionTypeRegistry.require_engine("alley"),
            RegistryKey,
        )
        self.assertIs(
            registry_key_target(
                ConnectionTypeEntry.model_fields["system_connection_type"].annotation,
            ),
            WorldConnectionTypeRegistry,
        )
        self.assertIs(registry_key_target(ConnectionTypeKey), WorldConnectionTypeRegistry)
        self.assertIsNot(
            registry_key_target(ConnectionTypeKey),
            registry_key_target(EconomyTierKey),
        )
        with self.assertRaises(Exception):
            ConnectionTypeEntry(system_connection_type="", display_name="x")

        conn = DistrictConnection(connection_type="road")
        self.assertIsInstance(conn.connection_type, RegistryKey)
        self.assertEqual(conn.connection_type, "road")
        self.assertIsInstance(DEFAULT_CONNECTION_TYPE, RegistryKey)
        self.assertEqual(
            DistrictConnection.street_default().connection_type,
            DEFAULT_CONNECTION_TYPE,
        )
        self.assertIs(
            registry_key_target(
                DistrictConnection.model_fields["connection_type"].annotation,
            ),
            WorldConnectionTypeRegistry,
        )
        with self.assertRaises(Exception):
            DistrictConnection(connection_type="")

        entry = DistrictTopologyEntry(
            node_uid="n1",
            x=0,
            y=0,
            z=0,
            role=DistrictEntryRole.ENTRY_POINT,
            facing=Facing.NORTH,
            connection_type="dirt_road",
        )
        self.assertIsInstance(entry.connection_type, RegistryKey)
        self.assertIs(
            registry_key_target(
                DistrictTopologyEntry.model_fields["connection_type"].annotation,
            ),
            WorldConnectionTypeRegistry,
        )

        engine_order = FrontageTypeOrder.canonical_defaults().order
        self.assertEqual(
            list(engine_order),
            ["highway", "road", "dirt_road", "alley", "trail"],
        )
        self.assertTrue(all(isinstance(k, RegistryKey) for k in engine_order))
        self.assertIs(
            registry_key_target(FrontageTypeOrder.model_fields["order"].annotation),
            WorldConnectionTypeRegistry,
        )
        self.assertIs(
            registry_key_target(
                DistrictTemplateEntry.model_fields["frontage_type_order"].annotation,
            ),
            WorldConnectionTypeRegistry,
        )
        self.assertIs(
            registry_key_target(
                SettlementSkeleton.model_fields["frontage_type_order"].annotation,
            ),
            WorldConnectionTypeRegistry,
        )
        self.assertIs(
            registry_key_target(
                BundleNamedLocation.model_fields["frontage_type_order"].annotation,
            ),
            WorldConnectionTypeRegistry,
        )

        skeleton = SettlementSkeleton(frontage_type_order=["road", "alley"])
        assert skeleton.frontage_type_order is not None
        self.assertIsInstance(skeleton.frontage_type_order[0], RegistryKey)
        loc = BundleNamedLocation(
            location_uid="loc-1",
            display_name="X",
            system_location_type="settlement",
            frontage_type_order=["highway"],
        )
        assert loc.frontage_type_order is not None
        self.assertIsInstance(loc.frontage_type_order[0], RegistryKey)
        district = DistrictTemplateEntry(
            system_name="inn_row",
            display_name="Inns",
            district_type="commercial",
            frontage_type_order=["road", "dirt_road"],
        )
        assert district.frontage_type_order is not None
        self.assertIsInstance(district.frontage_type_order[0], RegistryKey)
        with self.assertRaises(Exception):
            SettlementSkeleton(frontage_type_order=[""])


if __name__ == "__main__":
    unittest.main()
