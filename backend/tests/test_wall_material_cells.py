"""S6: selected wall materials reach the single wall writer — §8.7.1.

Generation-level gates: interior partitions carry the policy-selected room
material, the exterior shell keeps the building material; undecidable
regions fall back to the building material. Geometry, openings, floors and
determinism are regression gates — only wall `system_material` may differ.
"""
import unittest

from app.application.worldData.debugStructureRotations import RotationProbe
from app.application.worldData.generators.structure.cellBuilder import (
    build_level_cells,
)
from app.application.worldData.generators.structure.wallMaterials import (
    select_wall_materials,
)
from app.application.worldData.generators.structure.wallRegions import (
    classify_wall_regions,
)
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.dataModel.economy.materialPolicies import BuildingEconomicContext
from app.dataModel.locations.structure.enums.buildingElement import (
    StructureElement,
)
from tests.test_structure_orientation import test_world_building
from tests.test_u_shape_orientation_baseline import room
from tests.test_wall_material_baseline import (
    _partition_body,
    _split,
    _walls,
    _WORLD_MATERIALS,
    WallMaterialBaselineTests,
)


class WallMaterialCellsTests(unittest.TestCase):
    def _generate(self, world, building):
        probe = RotationProbe()
        layout = probe.generate_from_template(
            world, building, WallMaterialBaselineTests._two_room_template())
        return probe, layout

    def _world_building(self):
        world, building = test_world_building()
        world.material_registry = _WORLD_MATERIALS
        building.parent_wall_material = "iron"
        return world, building

    def _rooms(self, probe):
        return {r.room_id: r for r in probe.runtime_rooms if not r.is_shaft}

    def test_default_band_partition_gets_min_strength_room_material(self):
        world, building = self._world_building()
        # median tier of the 6-tier engine registry is quality → WEALTHY → min.
        probe, layout = self._generate(world, building)
        rooms = self._rooms(probe)
        body = _partition_body(rooms["hall"], rooms["chamber"])
        self.assertTrue(body)

        walls = _walls(layout.cells)
        # Passages may replace some partition cells with door cells.
        body_walls = {key: c for key, c in walls.items() if key[:2] in body}
        self.assertTrue(body_walls)
        for key, c in body_walls.items():
            self.assertEqual(c.system_material, "oak", f"partition {key}")
        self.assertTrue(all(c.system_material == "iron"
                            for key, c in walls.items()
                            if key[:2] not in body))

    def test_rich_building_partition_gets_max_strength_room_material(self):
        world, building = self._world_building()
        building.system_economic_tier = "exceptional"  # → RICH → max
        probe, layout = self._generate(world, building)
        rooms = self._rooms(probe)
        body = _partition_body(rooms["hall"], rooms["chamber"])
        self.assertTrue(body)
        walls = _walls(layout.cells)
        for key, c in walls.items():
            if key[:2] in body:
                self.assertEqual(c.system_material, "granite")

    def test_geometry_unchanged_only_wall_materials_differ(self):
        world, building = self._world_building()
        iron_probe, iron = self._generate(world, building)
        building.parent_wall_material = "stone"
        _, stone = self._generate(world, building)

        iron_geo, iron_mats = _split(iron.cells)
        stone_geo, stone_mats = _split(stone.cells)
        self.assertEqual(iron_geo, stone_geo)   # geometry identical
        self.assertEqual(iron.passages, stone.passages)

        rooms = self._rooms(iron_probe)
        body = _partition_body(rooms["hall"], rooms["chamber"])
        diffs = {xy for xy, m in iron_mats.items() if m != stone_mats[xy]}
        self.assertTrue(diffs)
        self.assertFalse(diffs & {(x, y, z) for x, y in body for z in range(4)})

    def test_openings_and_floors_keep_prior_materials(self):
        world, building = self._world_building()
        _, layout = self._generate(world, building)
        doors = [c for c in layout.cells
                 if c.system_building_element == StructureElement.DOOR]
        self.assertTrue(doors)
        self.assertEqual({c.system_material for c in doors}, {"oak"})
        floors = {c.system_material for c in layout.cells
                  if c.system_building_element == StructureElement.FLOOR}
        self.assertEqual(floors, {"oak", "granite"})

    def test_missing_strength_region_falls_back_to_building_material(self):
        world, building = self._world_building()
        world.material_registry = [
            dict(row) for row in _WORLD_MATERIALS if row["system_material"] == "oak"
        ] + [{"system_material": "granite", "display_name": "Granite",
              "material_category": "solid", "tags": ["construction"],
              "use_type": ["wall", "floor"], "economic_tier": "standard"}]
        probe, layout = self._generate(world, building)
        rooms = self._rooms(probe)
        body = _partition_body(rooms["hall"], rooms["chamber"])
        walls = _walls(layout.cells)
        self.assertTrue(all(c.system_material == "iron"
                            for key, c in walls.items()
                            if key[:2] in body))

    def test_deterministic_across_runs(self):
        world, building = self._world_building()
        _, first = self._generate(world, building)
        _, second = self._generate(world, building)
        self.assertEqual((first.cells, first.passages),
                         (second.cells, second.passages))

    def test_writer_override_preserves_default_for_unlisted_cells(self):
        a = room("a", x=0, y=0, width=7, depth=5)
        b = room("b", x=6, y=0, width=7, depth=5)
        uids = {a.uid_key: "room-a", b.uid_key: "room-b"}
        cells = build_level_cells(
            [a, b], [], 0, 3, "world", "bld", "iron", uids,
            {(6, 2): "oak"})
        walls = _walls(cells)
        self.assertEqual(walls[(6, 2, 0)].system_material, "oak")
        self.assertEqual(walls[(6, 2, 2)].system_material, "oak")
        self.assertEqual(walls[(6, 1, 0)].system_material, "iron")
        self.assertEqual(walls[(0, 0, 0)].system_material, "iron")

    def test_writer_output_matches_selector_plan(self):
        world, building = self._world_building()
        probe, layout = self._generate(world, building)
        level_rooms = [r for r in probe.runtime_rooms if r.placed]
        walls = _walls(layout.cells)

        regions = classify_wall_regions(level_rooms, 0, 3)
        plan = select_wall_materials(
            regions, {r.uid_key: r for r in level_rooms}, "iron",
            {e["system_material"]: e.get("structural_strength")
             for e in _WORLD_MATERIALS},
            BuildingEconomicContext(economic_tier="quality",
                                    band=EconomicTierBand.WEALTHY))
        self.assertFalse(plan.failures)
        expected = {(x, y): ch.system_material
                    for ch in plan.choices for x, y in ch.region.cells}
        checked = 0
        for (x, y, z), c in walls.items():
            if (x, y) in expected:
                self.assertEqual(c.system_material, expected[(x, y)],
                                 f"wall {(x, y, z)}")
                checked += 1
        self.assertTrue(checked)
