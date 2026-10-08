"""Internal facing fallback keeps geometry and reports degraded generation."""
import json
import tempfile
from app.application.jsonValidation.resolve import UnresolvedModelError, ResolveContext, resolve_result
from pydantic import ValidationError
import unittest
from pathlib import Path
from random import Random

from app.core.generationLogging import generation_world_log
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from app.dataModel.locations.structure.room.shapeParams import ResolvedStemWall
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

    def test_invalid_internal_direction_rejects_without_south_default(self):
        for value in (None, "", "bad", "any", "northeast", Facing.NORTHEAST, [], 12):
            with self.subTest(value=value), self.assertLogs("app.application.jsonValidation.resolve", "WARNING"), self.assertRaises(UnresolvedModelError):
                footprint_t_shape(0, 0, 6, 4, 2, value)

    def test_dispatch_does_not_hide_missing_direction(self):
        with self.assertRaises(UnresolvedModelError):
            room_footprint("t_shape", 0, 0, 6, 4)

    def test_pojo_missing_defaults_without_logging_and_invalid_rejects(self):
        with self.assertNoLogs(level="WARNING"):
            self.assertIs(ResolvedStemWall.model_validate({}).stem_wall, Facing.SOUTH)
            self.assertIs(ResolvedStemWall.model_validate({"stem_wall": "south"}).stem_wall, Facing.SOUTH)
            with self.assertRaises(ValidationError):
                ResolvedStemWall.model_validate({"stem_wall": "bad"})

    def test_corrupted_shape_source_rejects_before_room_generation(self):
        template = simple_structure()
        template.levels[0]["rooms"][0].update(shape_type="t_shape", shape_params={"stem_width_range": [2, 3]}, size={"width_range": [6, 6], "depth_range": [4, 4]})
        level = StructureGeneratorService._resolve_levels(template)[0]
        definition = level.rooms[0]
        invalid = definition.model_copy(update={"shape_params": definition.shape_params.model_copy(update={"stem_wall": "bad"})})
        level = level.model_copy(update={"rooms": [invalid]})
        world, _ = test_world_building()
        with self.assertRaises(UnresolvedModelError):
            instantiate_level_rooms(level, template, 5, 0, world, Random(42))
