"""Shared door height, runtime fallback diagnostics and connection plumbing."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from app.core.generationLogging import generation_world_log
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.passages.doorHeight import resolve_door_height
from app.application.worldData.generators.structure.passages.entry import _resolve_entry_height
from app.application.worldData.generators.structure.passages.doorway import _build_doorway
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.dataModel.locations.structure.room.entryPoint import EntryPoint
from app.dataModel.locations.structure.building.roomConnection import RoomConnection
from app.db.models.locationLevel import LocationLevel
from tests.structureWire import room_wire
from tests.test_structure_orientation import simple_structure, test_world_building
from tests.test_u_shape_orientation_baseline import room

LOGGER = "app.application.worldData.generators.structure.passages.doorHeight"
DOORWAY = "app.application.worldData.generators.structure.passages.doorway"


class DoorHeightTests(unittest.TestCase):
    def test_entry_low_explicit_resolves_formula_with_error(self):
        r = room()
        r.z_height = 8
        for explicit in (0, 1, -1):
            with self.subTest(explicit=explicit), self.assertLogs(LOGGER, "ERROR") as captured:
                height = _resolve_entry_height(r, EntryPoint(wall="east", passage_type="main_entrance",
                                               door_height=explicit), 2, simple_structure())
            self.assertEqual(height, 5)
            self.assertEqual(len(captured.records), 1)
            self.assertIn("auto-resolve", captured.output[0])

    def test_auto_floor_only_and_valid_explicit_bypasses_cap(self):
        custom = simple_structure().model_copy(update={"door_height_ratio": 0.2, "door_height_max": 1})
        self.assertEqual(resolve_door_height(8, None, 3, custom, context="test"), 3)
        with self.assertNoLogs(LOGGER, "ERROR"):
            for explicit in (3, 7):
                self.assertEqual(resolve_door_height(8, explicit, 3, custom, context="test"), explicit)
        for z, explicit in ((2, None), (8, 8), (8, 9)):
            with self.subTest(z=z, explicit=explicit), self.assertRaises(GenerationError):
                resolve_door_height(z, explicit, 2, custom, context="test")

    def connection(self, explicit, heights=(10, 6), template=None):
        fr, to = room("from"), room("to")
        fr.z_height, to.z_height = heights
        level = LocationLevel("level", "building", 0, max(heights), "Ground")
        conn = RoomConnection(from_room="from", to_room="to", passage_type="doorway", door_height=explicit)
        with patch(DOORWAY + "._shared_segment", return_value=[(1, 2)]), \
             patch(DOORWAY + ".DoorPlacer") as placer_class:
            placer = placer_class.return_value
            placer.filter_passable_from_center.return_value = [(1, 2)]
            placer.place.return_value = True
            passage = _build_doorway(conn, fr, to, level, level, {}, "world", "building", 2,
                                     template=template)
        self.assertIsNotNone(passage)
        return placer.place.call_args.kwargs["height"]

    def test_connection_uses_minimum_height_and_template_settings(self):
        for heights in ((10, 6), (6, 10)):
            self.assertEqual(self.connection(None, heights), 4)
            with self.assertLogs(LOGGER, "ERROR"):
                self.assertEqual(self.connection(1, heights), 4)
            self.assertEqual(self.connection(5, heights), 5)
            for explicit in (6, 7):
                with self.assertRaises(GenerationError):
                    self.connection(explicit, heights)
        custom = simple_structure().model_copy(update={"door_height_ratio": 0.5, "door_height_max": 3})
        self.assertEqual(self.connection(None, template=custom), 3)

    def test_generation_template_plumbing_determinism_immutability_and_transcript(self):
        world, building = test_world_building()
        template = simple_structure().model_copy(update={"door_height_ratio": 0.5, "door_height_max": 5})
        template.levels[0]["z_height"] = 10
        definition = template.levels[0]["rooms"][0]
        definition["size"]["z_range"] = [10, 10]
        definition["entry_point"]["door_height"] = 1
        template.levels[0]["rooms"].append(room_wire(room_id="guest",
            size={"width_range": [5, 5], "depth_range": [5, 5], "z_range": [8, 8]}))
        template.connections.append(dict(from_room="hall", to_room="guest", passage_type="doorway", door_height=1))
        before = deepcopy(template.model_dump())
        with tempfile.TemporaryDirectory() as directory:
            with generation_world_log(world.world_uid, mode="test", root=directory) as path:
                with patch(DOORWAY + ".resolve_door_height", wraps=resolve_door_height) as resolve:
                    first = StructureGeneratorService().generate_from_template(world, building, template)
                    second = StructureGeneratorService().generate_from_template(world, building, template)
            records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
        self.assertEqual(template.model_dump(), before)
        self.assertEqual((first.cells, first.transitions), (second.cells, second.transitions))
        self.assertEqual(resolve.call_count, 2)
        for call in resolve.call_args_list:
            self.assertEqual(call.args[0], 8)
            self.assertIs(call.args[3], template)
        errors = [r for r in records if r["level"] == "ERROR"]
        self.assertEqual(len(errors), 4)
        self.assertTrue(all(r["logger"] == LOGGER and "auto-resolve" in r["msg"] for r in errors))
