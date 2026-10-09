"""EntryPoint import contract, including the stdlib structure library."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from app.dataModel.spatial.facing import CARDINAL_FACINGS
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.entryAccessType import EntryAccessType
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.structure.room import EntryPoint
from tests.structureWire import room_wire, level_wire


class EntryPointTests(unittest.TestCase):
    def test_cardinals_and_entrance_types(self):
        for wall in CARDINAL_FACINGS:
            for kind in (TransitionType.MAIN_ENTRANCE, TransitionType.SERVICE_ENTRANCE):
                entry = EntryPoint.model_validate({"wall": wall.value, "passage_type": kind.value})
                self.assertEqual(entry.wall, wall)
                self.assertEqual(entry.passage_type, kind)
                self.assertEqual(entry.width, 1)
                self.assertEqual(entry.access_type, EntryAccessType.AUTO)
                self.assertIsNone(entry.door_height)

    def test_invalid_wire_is_rejected(self):
        valid = {"wall": "south", "passage_type": "main_entrance"}
        invalid = [
            {}, {"wall": "south"}, {"passage_type": "main_entrance"},
            {**valid, "wall": "northeast"}, {**valid, "width": 0},
            {**valid, "passage_type": "doorway"}, {**valid, "height": 3},
            {**valid, "unknown": True}, {**valid, "access_type": "invalid"},
        ]
        for wire in invalid:
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                EntryPoint.model_validate(wire)

    def test_full_wire_roundtrip_and_immutability(self):
        wire = dict(wall="east", passage_type="service_entrance", width=2,
                    door_height=4, frame_material="stone", panel_material=None,
                    access_type="steps")
        entry = EntryPoint.model_validate(wire)
        self.assertEqual(entry.model_dump(mode="json"), wire)
        with self.assertRaises(ValidationError):
            entry.width = 3

    def test_structure_validates_both_fields_without_changing_wire(self):
        for field in ("entry_point", "back_entry_point"):
            wire = {
                "system_name": "00000000-0000-4000-8000-000000000001",
                "display_name": "Test",
                "levels": [level_wire(rooms=[room_wire(**{field: {
                    "wall": "west", "passage_type": "service_entrance",
                }})])],
            }
            original = deepcopy(wire)
            structure = StructureTemplate.model_validate(wire)
            self.assertEqual(wire, original)
            self.assertEqual(structure.levels, wire["levels"])
            wire["levels"][0]["rooms"][0][field] = {}
            with self.assertRaises(ValidationError) as error:
                StructureTemplate.model_validate(wire)
            self.assertIn("hall", str(error.exception))
            self.assertIn(field, str(error.exception))

    def test_all_stdlib_structures_validate(self):
        from app.application.worldData.libraryPacks.manifest import PACK_MANIFEST_FILENAME
        root = Path(__file__).resolve().parents[2] / "structures_templates/base"
        paths = [p for p in root.glob("*.json") if p.name != PACK_MANIFEST_FILENAME]
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.name):
                StructureTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))
