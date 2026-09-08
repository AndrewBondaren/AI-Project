"""PlacementCondition wire types — RegistryKey terrain/tier, CellZone, bare district_type."""

from __future__ import annotations

import unittest

from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.registryKey import RegistryKey
from app.dataModel.settlement.district.cellZone import CellZone
from app.dataModel.settlement.district.placementCondition import (
    PlacementCondition,
    PlacementConditionType,
)
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


class TestPlacementConditionTyping(unittest.TestCase):
    def test_wire_strings_coerce(self) -> None:
        cond = PlacementCondition(
            type="adjacent_terrain",
            terrain_types=["liquid_body"],
            min_adjacent_cells=1,
        )
        self.assertIs(cond.type, PlacementConditionType.ADJACENT_TERRAIN)
        self.assertEqual(len(cond.terrain_types or []), 1)
        key = (cond.terrain_types or [])[0]
        self.assertIsInstance(key, RegistryKey)
        self.assertEqual(key, "liquid_body")

        tiered = PlacementCondition(type="economic_tier_min", tier="standard")
        self.assertIsInstance(tiered.tier, RegistryKey)
        self.assertEqual(tiered.tier, "standard")

        zoned = PlacementCondition(type="cell_zone", zone="center")
        self.assertIs(zoned.zone, CellZone.CENTER)

    def test_empty_registry_keys_rejected(self) -> None:
        with self.assertRaises(Exception):
            PlacementCondition(type="adjacent_terrain", terrain_types=[""])
        with self.assertRaises(Exception):
            PlacementCondition(type="economic_tier_min", tier="")

    def test_district_type_stays_str(self) -> None:
        cond = PlacementCondition(type="requires_district_type", district_type="civic")
        self.assertEqual(cond.district_type, "civic")
        inner = unwrap_wire_type(PlacementCondition.model_fields["district_type"].annotation)
        self.assertIn("str", str(inner))
        self.assertNotIsInstance(cond.district_type, RegistryKey)

    def test_canonical_templates_construct(self) -> None:
        registry = WorldDistrictTemplateRegistry.canonical_defaults()
        civic = next(e for e in registry.root if e.system_name == "civic_center")
        zone_cond = next(c for c in civic.placement_conditions if c.type is PlacementConditionType.CELL_ZONE)
        self.assertIs(zone_cond.zone, CellZone.CENTER)

        port = next(e for e in registry.root if e.system_name == "port_district")
        terrain_cond = next(
            c for c in port.placement_conditions if c.type is PlacementConditionType.ADJACENT_TERRAIN
        )
        self.assertEqual(terrain_cond.terrain_types, ["liquid_body"])
        self.assertIsInstance((terrain_cond.terrain_types or [])[0], RegistryKey)
        liquid = WorldTerrainRegistry.canonical_defaults().entry_for("liquid_body")
        assert liquid is not None
        self.assertEqual((terrain_cond.terrain_types or [])[0], liquid.system_terrain)

        size_cond = next(
            c for c in port.placement_conditions if c.type is PlacementConditionType.MIN_CITY_SIZE
        )
        self.assertIsInstance(size_cond.size, RegistryKey)
        self.assertEqual(size_cond.size, WorldSettlementSizeRegistry.default_system_size())
        self.assertIs(
            type(size_cond.size),
            type(WorldSettlementSizeRegistry.default_system_size()),
        )


if __name__ == "__main__":
    unittest.main()
