"""RoomConnection import contract and runtime boundary — building generator §3.7."""
import unittest
from copy import deepcopy

from pydantic import ValidationError

from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.structureGeneratorService import (
    StructureGeneratorService,
)
from app.dataModel.structure.building.roomConnection import (
    DEFAULT_ARCHWAY_WIDTH,
    DEFAULT_DOORWAY_WIDTH,
    RoomConnection,
)
from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.dataModel.structure.enums.passageType import PassageType

_VALID = {"from_room": "hall", "to_room": "kitchen", "passage_type": "doorway"}
_UID = "00000000-0000-4000-8000-000000000007"


class RoomConnectionTests(unittest.TestCase):
    def test_defaults_and_per_kind_width(self):
        door = RoomConnection.model_validate(_VALID)
        self.assertEqual(door.width, DEFAULT_DOORWAY_WIDTH)
        self.assertFalse(door.required)
        self.assertIsNone(door.door_height)
        self.assertIsNone(door.frame_material)
        self.assertIsNone(door.step_material)

        arch = RoomConnection.model_validate({**_VALID, "passage_type": "archway"})
        self.assertEqual(arch.width, DEFAULT_ARCHWAY_WIDTH)
        explicit = RoomConnection.model_validate(
            {**_VALID, "passage_type": "archway", "width": 4})
        self.assertEqual(explicit.width, 4)

    def test_invalid_wire_is_rejected(self):
        invalid = [
            {}, {"from_room": "a"},
            {k: v for k, v in _VALID.items() if k != "from_room"},
            {k: v for k, v in _VALID.items() if k != "to_room"},
            {k: v for k, v in _VALID.items() if k != "passage_type"},
            {**_VALID, "width": 0},
            {**_VALID, "height": 3},
            {**_VALID, "unknown": True},
        ]
        for wire in invalid:
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                RoomConnection.model_validate(wire)

    def test_non_horizontal_passage_type_falls_back_to_doorway(self):
        for raw in ("staircase", "main_entrance", "service_entrance",
                    "bogus", None, PassageType.STAIRCASE):
            with self.subTest(raw=raw):
                conn = RoomConnection.model_validate({**_VALID, "passage_type": raw})
            self.assertIs(conn.passage_type, PassageType.DOORWAY)
            self.assertEqual(conn.width, DEFAULT_DOORWAY_WIDTH)

    def test_full_wire_roundtrip_and_immutability(self):
        wire = dict(from_room="a", to_room="b", passage_type="doorway",
                    required=True, width=2, door_height=4, frame_material="stone",
                    panel_material=None, step_material="oak", railing_material=None)
        conn = RoomConnection.model_validate(wire)
        self.assertEqual(conn.model_dump(mode="json"), wire)
        with self.assertRaises(ValidationError):
            conn.width = 3

    def test_structure_validates_connections_without_changing_wire(self):
        wire = {
            "system_name": _UID,
            "display_name": "Test",
            "connections": [dict(_VALID)],
        }
        original = deepcopy(wire)
        structure = StructureTemplate.model_validate(wire)
        self.assertEqual(wire, original)
        self.assertEqual(structure.connections, wire["connections"])

        wire["connections"] = [{"from_room": "hall"}]
        with self.assertRaises(ValidationError) as error:
            StructureTemplate.model_validate(wire)
        self.assertIn("connections[0]", str(error.exception))

    def test_staircase_conn_survives_import_as_doorway(self):
        wire = {"system_name": _UID, "display_name": "Test",
                "connections": [{"from_room": "hall", "to_room": "kitchen",
                                 "passage_type": "staircase"}]}
        template = StructureTemplate.model_validate(wire)
        self.assertEqual(template.connections, wire["connections"])
        with self.assertLogs(
            "app.application.worldData.generators.structure."
            "structureGeneratorService", "ERROR",
        ) as capture:
            resolved = StructureGeneratorService._resolve_connections(template)
        self.assertIs(resolved[0].passage_type, PassageType.DOORWAY)
        self.assertIn("staircase", capture.output[0])
        self.assertIn("connections[0]", capture.output[0])

    def test_runtime_boundary_raises_generation_error(self):
        template = StructureTemplate.model_construct(
            system_name=_UID, display_name="Test",
            connections=[{"from_room": "hall"}],
        )
        with self.assertRaises(GenerationError) as error:
            StructureGeneratorService._resolve_connections(template)
        self.assertIn("connections[0]", str(error.exception))
        self.assertIn(_UID, str(error.exception))

    def test_runtime_boundary_returns_typed_list(self):
        wire = {"system_name": _UID, "display_name": "Test",
                "connections": [dict(_VALID), {**_VALID, "passage_type": "archway"}]}
        template = StructureTemplate.model_validate(wire)
        resolved = StructureGeneratorService._resolve_connections(template)
        self.assertTrue(all(isinstance(c, RoomConnection) for c in resolved))
        self.assertEqual(resolved[0].passage_type, PassageType.DOORWAY)
        self.assertEqual(resolved[1].width, DEFAULT_ARCHWAY_WIDTH)


if __name__ == "__main__":
    unittest.main()
