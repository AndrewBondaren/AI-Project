"""Step 3b: plot band and body cross the building/geometry boundary."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import derive_structure_context
from app.application.worldData.generators.assemblers.buildingAssembler.assemblerRegistry import BUILDING_ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.buildingAssembler.buildingAssembler import BuildingAssembler
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.dataModel.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class BuildingAssemblerTests(unittest.TestCase):
    def setUp(self):
        self.world = World(
            world_uid="band-world", name="Band test", created_at="2026-09-27",
            economic_tier_registry=[
                {"system_tier": tier, "display_tier": tier, "base_value": i}
                for i, tier in enumerate(("low", "median", "high"))
            ],
            material_registry=[
                {
                    "system_material": tier + "_stone", "display_name": tier,
                    "material_category": "solid", "tags": ["construction"],
                    "use_type": ["wall", "floor"], "economic_tier": tier,
                }
                for tier in ("low", "median", "high")
            ],
        )
        self.building = NamedLocation(
            location_uid="band-building", world_uid=self.world.world_uid,
            display_name="Building", system_location_type="building",
            created_at="2026-09-27", map_x=0, map_y=0, map_z=7,
        )
        self.structure = StructureTemplate(
            system_name="00000000-0000-4000-8000-000000000001",
            display_name="Single room",
            levels=[{
                "z_offset": 0, "display_name": "Ground",
                "rooms": [{
                    "room_id": "hall", "display_name": "Hall", "room_type": "common_hall",
                    "shape_type": "square", "size": {"width_range": [5, 5]},
                    "required": True, "is_public": True, "is_forbidden": False,
                }],
            }],
        )
        self.body = BuildingBodyTemplate(
            structure=self.structure.system_name, foundation_type="none", roof_type="none",
        )

    def context(self, band):
        plot = PlotLayoutTemplate(
            system_name="band-plot", display_name="Plot", main_building=self.body,
            economic_tier_band=band,
        )
        skeleton = CitySkeleton(None, None, None, None, None, None)
        return derive_structure_context(
            plot, skeleton, AreaSlot([(0, 0)], 7, Facing.SOUTH), None, ground_z=7,
        )

    def test_plot_band_selects_room_material_through_real_generation(self):
        for band, expected in (("rich", "high_stone"), ("poor", "low_stone"), (None, "median_stone")):
            with self.subTest(band=band), patch.object(TierResolver, "resolve", wraps=TierResolver.resolve) as resolve:
                layout = BuildingAssembler().assemble(
                    self.world, self.building, self.body, self.structure, self.context(band),
                )
                self.assertEqual(len(layout.rooms), 1)
                self.assertEqual(layout.rooms[0].parent_wall_material, expected)
                self.assertEqual(layout.rooms[0].parent_floor_material, expected)
                self.assertTrue(layout.cells)
                calls = [c for c in resolve.call_args_list if c.kwargs.get("building") is self.building]
                self.assertEqual(len(calls), 4)
                self.assertTrue(all(c.kwargs["building_band"] == band for c in calls))

    def test_explicit_building_tier_overrides_band(self):
        self.building.system_economic_tier = "low"
        layout = BuildingAssembler().assemble(
            self.world, self.building, self.body, self.structure, self.context("rich"),
        )
        self.assertEqual(layout.rooms[0].parent_wall_material, "low_stone")

    def test_body_controls_envelope_without_mutating_runtime_context(self):
        context = replace(self.context("rich"), foundation_type="slab", roof_type="gable")
        with patch.object(BuildingAssembler, "attach_envelope", wraps=BuildingAssembler.attach_envelope) as attach:
            BuildingAssembler().assemble(self.world, self.building, self.body, self.structure, context)
        effective = attach.call_args.args[3]
        self.assertEqual((effective.foundation_type, effective.roof_type), ("none", "none"))
        self.assertEqual((effective.ground_z, effective.building_band, effective.facing), (7, "rich", Facing.SOUTH))
        self.assertEqual((context.foundation_type, context.roof_type), ("slab", "gable"))

    def test_registry_keeps_all_kinds_with_new_contract(self):
        self.assertEqual(set(BUILDING_ASSEMBLER_REGISTRY.all()), {"building", "ruins", "vastHull", "resourceExtraction"})
        for kind in ("ruins", "vastHull", "resourceExtraction"):
            with self.subTest(kind=kind), self.assertRaises(NotImplementedError):
                BUILDING_ASSEMBLER_REGISTRY.get(kind).assemble(
                    self.world, self.building, self.body, self.structure, self.context("rich"),
                )

    def test_direct_generator_accepts_structure_and_band(self):
        layout = StructureGeneratorService().generate_from_template(
            self.world, self.building, structure=self.structure, building_band="rich",
        )
        self.assertEqual(layout.rooms[0].parent_wall_material, "high_stone")
