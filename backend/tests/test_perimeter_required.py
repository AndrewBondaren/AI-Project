"""A2: warn only for an explicit false overridden by an entrance."""
import json
import logging
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from random import Random
from unittest.mock import patch

from app.core.generationLogging import generation_world_log
from app.application.worldData.generators.structure.room.roomFactory import instantiate_level_rooms
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from tests.test_structure_orientation import simple_structure, test_world_building

LOGGER = "app.application.worldData.generators.structure.room.roomFactory"


class PerimeterRequiredTests(unittest.TestCase):
    def instantiate(self, template):
        level = StructureGeneratorService._resolve_levels(template)[0]
        world, _ = test_world_building()
        with patch(LOGGER + ".resolve_room_materials", return_value=("stone", "wood")):
            return instantiate_level_rooms(level, template, 5, 0, world, Random(1))

    def test_explicit_false_warns_for_either_entrance_and_forces_true(self):
        for field in ("entry_point", "back_entry_point"):
            with self.subTest(field=field):
                template = simple_structure()
                wire = template.levels[0]["rooms"][0]
                wire[field] = wire.pop("entry_point")
                wire["perimeter_required"] = False
                before = deepcopy(template.model_dump())
                with self.assertLogs(LOGGER, "WARNING") as captured:
                    rooms = self.instantiate(template)
                self.assertEqual(len(captured.records), 1)
                self.assertEqual(captured.records[0].levelno, logging.WARNING)
                self.assertIn("perimeter_required=false ignored", captured.output[0])
                self.assertIn("hall", captured.output[0])
                self.assertIs(rooms[0].perimeter_required, True)
                self.assertEqual(template.model_dump(), before)

    def test_omitted_true_and_false_without_entrance_are_quiet(self):
        for has_entry, value in ((True, None), (True, True), (False, False), (False, None)):
            with self.subTest(has_entry=has_entry, value=value):
                template = simple_structure()
                wire = template.levels[0]["rooms"][0]
                if not has_entry:
                    wire.pop("entry_point")
                if value is not None:
                    wire["perimeter_required"] = value
                with self.assertNoLogs(LOGGER, "WARNING"):
                    rooms = self.instantiate(template)
                self.assertIs(rooms[0].perimeter_required, has_entry)

    def test_warning_reaches_transcript_once_per_definition_with_both_entries(self):
        template = simple_structure()
        wire = template.levels[0]["rooms"][0]
        wire.update(perimeter_required=False, count=2,
                    back_entry_point={"wall": "west", "passage_type": "service_entrance"})
        with tempfile.TemporaryDirectory() as directory:
            with generation_world_log("perimeter-test", mode="test", root=directory) as path:
                rooms = self.instantiate(template)
            records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
        warnings = [r for r in records if r["logger"] == LOGGER and r["level"] == "WARNING"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("perimeter_required=false", warnings[0]["msg"])
        self.assertEqual(len(rooms), 2)
        self.assertTrue(all(r.perimeter_required is True for r in rooms))
