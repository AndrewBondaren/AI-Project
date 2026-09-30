"""Internal facing fallback keeps geometry and reports degraded generation."""
import json
import tempfile
import unittest
from pathlib import Path
from random import Random

from app.core.generationLogging import generation_world_log
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from app.dataModel.structure.room.shapeParams import ResolvedStemWall
from app.application.worldData.generators.structure.shapes import footprint_t_shape, room_footprint
from app.application.worldData.generators.structure.room.roomFactory import instantiate_level_rooms
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from tests.test_structure_orientation import simple_structure, test_world_building

LOGGER = "app.application.worldData.generators.structure.shapes"


class FacingDefaultsTests(unittest.TestCase):
    def test_cardinals_preserve_geometry_without_logs(self):
        for wall in CARDINAL_FACINGS:
            with self.subTest(wall=wall), self.assertNoLogs(LOGGER, level="WARNING"):
                result = footprint_t_shape(10, 20, 6, 4, 2, wall)
                self.assertEqual(result, footprint_t_shape(10, 20, 6, 4, 2, wall.value))
                self.assertEqual(len(result), 32)
                expected_tip = {Facing.SOUTH: (12, 16), Facing.NORTH: (12, 27),
                                Facing.WEST: (6, 21), Facing.EAST: (19, 21)}[wall]
                self.assertIn(expected_tip, result)

    def test_invalid_or_unresolved_direction_uses_south_and_logs(self):
        expected = footprint_t_shape(0, 0, 6, 4, 2, Facing.SOUTH)
        for value in (None, "", "bad", "any", "northeast", Facing.NORTHEAST, [], 12):
            with self.subTest(value=value), self.assertLogs(LOGGER, level="ERROR") as captured:
                result = footprint_t_shape(0, 0, 6, 4, 2, value)
            self.assertEqual(result, expected)
            self.assertEqual(len(captured.records), 1)
            self.assertIn("south", captured.output[0])

    def test_dispatch_does_not_hide_missing_direction(self):
        with self.assertLogs(LOGGER, level="ERROR"):
            result = room_footprint("t_shape", 0, 0, 6, 4)
        self.assertEqual(result, footprint_t_shape(0, 0, 6, 4, 2, Facing.SOUTH))

    def test_pojo_marks_fallback_without_logging(self):
        with self.assertNoLogs(level="WARNING"):
            missing = ResolvedStemWall.model_validate({})
            invalid = ResolvedStemWall.model_validate({"stem_wall": "bad"})
            valid = ResolvedStemWall.model_validate({"stem_wall": "south"})
        self.assertIs(missing.stem_wall, Facing.SOUTH)
        self.assertTrue(missing.substituted)
        self.assertTrue(invalid.substituted)
        self.assertFalse(valid.substituted)

    def test_mixed_array_keeps_geometry_and_logs_once_before_repeated_footprints(self):
        template = simple_structure()
        wire = template.levels[0]["rooms"][0]
        wire.update(shape_type=["t_shape", "t_shape"],
                    shape_params={"stem_width_range": [2, 3]},
                    size={"width_range": [6, 6], "depth_range": [4, 4]})
        level = StructureGeneratorService._resolve_levels(template)[0]
        world, _ = test_world_building()
        # The old mixed-array path resolved no shape params and consumed no RNG
        # for them. Keep that path; only add a deterministic diagnostic fallback.
        rng = Random(42)
        with tempfile.TemporaryDirectory() as directory:
            with generation_world_log(world.world_uid, mode="test", root=directory) as path:
                instances = instantiate_level_rooms(level, template, 5, 0, world, rng)
                instance = instances[0]
                self.assertIs(instance.shape_params["stem_wall"], Facing.SOUTH)
                self.assertNotIn("stem_width", instance.shape_params)
                instance.origin_x = instance.origin_y = 0
                footprint = instance.get_footprint()
                self.assertEqual(footprint, instance.get_footprint())
            records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
        errors = [r for r in records if r["level"] == "ERROR" and r["logger"] == LOGGER]
        self.assertEqual(len(errors), 1)
        self.assertIn(str(template.system_name), errors[0]["msg"])
        self.assertIn("hall", errors[0]["msg"])
        self.assertEqual(footprint, footprint_t_shape(0, 0, 6, 4, 2, Facing.SOUTH))
