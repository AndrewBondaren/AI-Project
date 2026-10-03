"""3c-RNG: UUID compatibility and staircase-scoped replay."""

import importlib
import json
import unittest
from dataclasses import replace
from pathlib import Path
from random import Random
from unittest.mock import patch
from uuid import NAMESPACE_DNS, uuid5

from app.application.worldData.generators.structure.staircase.uShape.uShapeHelper import _compute_fr_anchor, _compute_u_params
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.buildingElement import StructureElement
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.utils.deterministicIds import det_uuid, scoped_rng


class DeterministicIdsTests(unittest.TestCase):
    def test_uuid_formula_and_existing_imports_are_compatible(self):
        modules = (
            ("generators.structure.structureGeneratorService", "_det_uuid"),
            ("generators.structure.passages.shared", "_det_uuid"),
            ("generators.structure.passages.staircaseTunnelOrchestrator", "_det_uuid"),
            ("generators.structure.staircase.builder", "_det_uuid"),
            ("generators.structure.staircase.surfaceCorridor", "_det_uuid"),
            ("settlementOutdoor.settlementOutdoorUids", "_uuid5"),
        )
        for parts in (("a", "b"), ("building", "level_0"), ("city", "district|core|2"), ("дом", "room", "0")):
            expected = str(uuid5(NAMESPACE_DNS, "|".join(parts)))
            self.assertEqual(det_uuid(*parts), expected)
            for module, name in modules:
                with self.subTest(module=module, parts=parts):
                    helper = getattr(importlib.import_module("app.application.worldData." + module), name)
                    self.assertIs(helper, det_uuid)
                    self.assertEqual(helper(*parts), expected)

    def test_rng_replays_and_is_independent_of_other_streams(self):
        parts = ("building", "stairs", "fr_anchor")
        first = scoped_rng(*parts)
        expected = [first.random() for _ in range(8)]
        other = scoped_rng("other-building", "stairs", "fr_anchor")
        for _ in range(100):
            other.random()
        replay = scoped_rng(*parts)
        self.assertEqual(expected, [replay.random() for _ in range(8)])
        self.assertNotEqual(expected[0], scoped_rng("other-building", "stairs", "fr_anchor").random())
        self.assertEqual(expected[0], Random(det_uuid(*parts)).random())

    def test_anchor_keeps_free_corner_fallback_and_previous_corner(self):
        args = (10, 20, 3, 3, Facing.NORTH)
        selected, _, _ = _compute_fr_anchor(*args, rng=scoped_rng("b", "s"))
        cells = {(*selected, 0): MapCell("w", *selected, 0, system_building_element=StructureElement.WALL)}
        fallback, _, _ = _compute_fr_anchor(*args, cells=cells, rng=scoped_rng("b", "s"))
        self.assertNotEqual(selected, fallback)
        previous, _, _ = _compute_fr_anchor(*args, prev_fr_anchor=selected, cells=cells, rng=scoped_rng("different"))
        self.assertEqual(previous, selected)

    def test_generate_replays_u_shape_anchors_and_cells(self):
        path = Path(__file__).resolve().parents[2] / "structures_templates/base/7c3a4d5e-6f7a-4b8c-8d9e-1f2a3b4c5d6e.json"
        structure = StructureTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))
        original = structure.model_dump()
        world = World(world_uid="rng-world", name="RNG", created_at="2026-09-29")
        building = NamedLocation(
            location_uid="rng-building", world_uid=world.world_uid,
            display_name="Manor", system_location_type="building", created_at="2026-09-29",
            map_x=20, map_y=30, map_z=7,
        )
        module = "app.application.worldData.generators.structure.staircase.uShape.uShape"

        def generate():
            anchors = []

            def capture(*args, **kwargs):
                params = _compute_u_params(*args, **kwargs)
                anchors.append(params.fr_anchor)
                return params

            with patch(module + "._compute_u_params", side_effect=capture), patch("random.choice", side_effect=AssertionError("global RNG used")):
                layout = StructureGeneratorService().generate_from_template(world, building, structure)
            self.assertTrue(anchors)
            stairs = [c for c in layout.cells if c.system_building_element in (
                StructureElement.STAIRCASE, StructureElement.STAIR_ANCHOR, StructureElement.STAIR_FLOOR,
            )]
            self.assertTrue(stairs)
            return anchors, stairs, layout

        first = generate()
        second = generate()
        self.assertEqual(first[:2], second[:2])
        before, after = first[2], second[2]
        self.assertEqual(before.cells, after.cells)
        self.assertEqual(before.levels, after.levels)
        self.assertEqual(before.passages, after.passages)
        self.assertEqual(before.occupied_footprint, after.occupied_footprint)
        self.assertEqual(
            [replace(room, created_at="") for room in before.rooms],
            [replace(room, created_at="") for room in after.rooms],
        )
        self.assertEqual(structure.model_dump(), original)
