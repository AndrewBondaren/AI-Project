"""CITY-T-5n/5o 4a: generate at placement before resolving the threshold."""

import unittest
from unittest.mock import patch

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import AreaThresholdKind
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import StructureAreaAssembler
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.dataModel.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.structure.building.structureCatalog import StructureCatalog
from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.dataModel.structure.enums.passageType import PassageType
from app.db.models.mapCell import MapCell
from app.db.models.world import World


class StructureAreaAssemblerTests(unittest.TestCase):
    def setUp(self):
        self.world = World(world_uid="area-world", name="Area", created_at="2026-09-29")
        self.skeleton = CitySkeleton(None, None, None, None, None, None)
        self.structure = StructureTemplate(
            system_name="00000000-0000-4000-8000-000000000041",
            display_name="Room with entrance",
            levels=[{
                "z_offset": 0, "display_name": "Ground",
                "rooms": [{
                    "room_id": "hall", "display_name": "Hall", "room_type": "common_hall",
                    "shape_type": "square", "size": {"width_range": [5, 5]},
                    "required": True, "is_public": True, "is_forbidden": False,
                    "entry_point": {"wall": "south", "passage_type": "main_entrance"},
                }],
            }],
        )
        self.catalog = StructureCatalog([self.structure])
        self.plot = PlotLayoutTemplate(
            system_name="area-plot", display_name="Plot", economic_tier_band="rich",
            occupied_footprint={"min_x": 0, "min_y": 0, "width": 5, "depth": 5},
            main_building=BuildingBodyTemplate(
                structure=self.structure.system_name, foundation_type="none", roof_type="none",
            ),
        )

    def assemble(self, *, x=20, y=30, facing=Facing.SOUTH, terrain=None, street=frozenset(), plot=None):
        slot = AreaSlot([(xx, yy) for xx in range(x, x + 5) for yy in range(y, y + 5)], 7, facing)
        return StructureAreaAssembler().assemble(
            self.world, slot, self.plot if plot is None else plot, self.skeleton, terrain,
            structure_catalog=self.catalog, building_x=x, building_y=y, street_xy=street,
        )

    def entry(self, layout):
        entries = [p for p in layout.passages if p.from_level_uid is None
                   and p.system_passage_type == PassageType.MAIN_ENTRANCE]
        self.assertEqual(len(entries), 1)
        return entries[0]

    def test_real_entry_becomes_threshold_in_world_coordinates(self):
        generate = StructureGeneratorService.generate_from_template
        calls = []

        def capture(service, world, building, structure, **kwargs):
            calls.append((building, structure, kwargs))
            return generate(service, world, building, structure, **kwargs)

        with patch.object(StructureGeneratorService, "generate_from_template", capture):
            area = self.assemble(facing=Facing.EAST)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], area.building_location)
        self.assertIs(calls[0][1], self.structure)
        self.assertNotIn("facing", calls[0][2])
        self.assertEqual(calls[0][2]["building_band"], "rich")
        entry = self.entry(area.building_layout)
        self.assertEqual(area.threshold.kind, AreaThresholdKind.DOOR)
        self.assertEqual(area.threshold.cells, [(entry.to_x, entry.to_y)])
        self.assertEqual(entry.to_y, 30)  # Author's SOUTH entry despite EAST slot.
        self.assertTrue(20 <= entry.to_x < 25)
        self.assertEqual(len(area.building_layout.rooms), 1)
        self.assertTrue(area.building_layout.cells)
        self.assertEqual(area.building_layout.rooms[0].parent_location_uid, area.building_location.location_uid)

    def test_same_structure_at_two_origins_has_distinct_room_uids(self):
        first, second = self.assemble(), self.assemble(x=40)
        self.assertNotEqual(first.building_layout.rooms[0].location_uid, second.building_layout.rooms[0].location_uid)
        a, b = self.entry(first.building_layout), self.entry(second.building_layout)
        self.assertEqual((b.to_x - a.to_x, b.to_y - a.to_y), (20, 0))

    def test_public_plot_without_building_has_no_geometry(self):
        plot = self.plot.model_copy(update={"main_building": None, "plot_type": "public"})
        with patch.object(StructureGeneratorService, "generate_from_template") as generate:
            area = self.assemble(plot=plot)
        generate.assert_not_called()
        self.assertIsNone(area.building_location)
        self.assertIsNone(area.building_layout)
        self.assertEqual(area.threshold.kind, AreaThresholdKind.PARCEL_EDGE)

    def test_missing_structure_reports_plot_and_structure(self):
        self.catalog = StructureCatalog.empty()
        with self.assertRaises(GenerationError) as ctx:
            self.assemble()
        self.assertIn(self.plot.system_name, str(ctx.exception))
        self.assertIn(self.structure.system_name, str(ctx.exception))

    def test_clamp_translates_generated_layout_only_in_z(self):
        baseline = self.assemble()
        entry = self.entry(baseline.building_layout)
        street = (entry.to_x, entry.to_y - 1)
        terrain = [MapCell(self.world.world_uid, x, y, 7) for x, y in baseline.slot.cells]
        terrain.append(MapCell(self.world.world_uid, *street, 0))
        clamped = self.assemble(terrain=terrain, street={street})
        dz = clamped.building_location.map_z - baseline.building_location.map_z
        self.assertLess(dz, 0)
        before, after = baseline.building_layout, clamped.building_layout
        self.assertEqual([(c.x, c.y, c.z + dz) for c in before.cells], [(c.x, c.y, c.z) for c in after.cells])
        self.assertEqual([r.map_z + dz for r in before.rooms], [r.map_z for r in after.rooms])
        self.assertEqual([lv.z + dz for lv in before.levels], [lv.z for lv in after.levels])
        self.assertEqual(before.passages, after.passages)
        self.assertEqual(before.occupied_footprint, after.occupied_footprint)
