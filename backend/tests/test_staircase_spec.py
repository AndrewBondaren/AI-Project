"""StaircaseSpec import contract and runtime boundary — building generator §3.7b."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.structureGeneratorService import (
    StructureGeneratorService,
)
from app.dataModel.locations.structure.building.staircaseSpec import ShaftSize, StaircaseSpec
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.staircaseType import StaircaseType

_VALID = {"stops": ["hall", "corridor"]}
_UID = "00000000-0000-4000-8000-000000000009"


class StaircaseSpecTests(unittest.TestCase):
    def test_defaults_and_auto_id(self):
        spec = StaircaseSpec.model_validate(_VALID)
        self.assertEqual(spec.staircase_id, "staircase_hall_corridor")
        self.assertIs(spec.staircase_type, StaircaseType.U_SHAPE)
        self.assertFalse(spec.has_walls)
        self.assertFalse(spec.in_a_room)
        self.assertFalse(spec.outside)
        self.assertFalse(spec.on_the_edge)
        self.assertFalse(spec.is_movable)
        self.assertFalse(spec.has_trapdoor)
        self.assertFalse(spec.near_wall)
        self.assertFalse(spec.closed_exit)
        self.assertIsNone(spec.step_material)
        self.assertIsNone(spec.size)
        self.assertIsNone(spec.facing)
        self.assertIsNone(spec.embed_in)
        self.assertIsNone(spec.embed_at)
        self.assertIsNone(spec.open_wall_shaft)

    def test_explicit_id_and_stops_none_fallbacks(self):
        spec = StaircaseSpec.model_validate({**_VALID, "staircase_id": "main_stair"})
        self.assertEqual(spec.staircase_id, "main_stair")

        for raw, expected in (
            ({"staircase_id": "", **_VALID}, "staircase_hall_corridor"),
            ({}, "staircase"),
            ({"stops": ["only"]}, "staircase"),
        ):
            spec = StaircaseSpec.model_validate(raw)
            self.assertEqual(spec.staircase_id, expected)

    def test_staircase_type_wire(self):
        for raw, expected in (
            ("u_shape", StaircaseType.U_SHAPE),
            ("spiral", StaircaseType.SPIRAL),
            ("straight", StaircaseType.STRAIGHT),
            ("vertical_ladder", StaircaseType.VERTICAL_LADDER),
            ("external_vertical_ladder", StaircaseType.EXTERNAL_VERTICAL_LADDER),
            ("trapdoor", StaircaseType.VERTICAL_LADDER),
            (None, StaircaseType.U_SHAPE),
        ):
            with self.subTest(raw=raw):
                spec = StaircaseSpec.model_validate({**_VALID, "staircase_type": raw})
                self.assertIs(spec.staircase_type, expected)

    def test_invalid_wire_is_rejected(self):
        invalid = [
            {"stops": "hall"},
            {**_VALID, "staircase_type": "bogus"},
            {**_VALID, "facing": "north_east"},
            {**_VALID, "facing": "bogus"},
            {**_VALID, "embed_at": "north"},
            {**_VALID, "embed_at": "bogus"},
            {**_VALID, "outside": True},
            {**_VALID, "outside": True, "has_walls": False},
            {**_VALID, "in_a_room": True, "outside": True, "has_walls": True},
            {**_VALID, "size": {}},
            {**_VALID, "size": {"size_type": "sq_small", "width_range": [4, 4]}},
            {**_VALID, "unknown": True},
        ]
        for wire in invalid:
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                StaircaseSpec.model_validate(wire)

    def test_flag_compat_accepts_valid_combos(self):
        for wire in (
            {**_VALID, "outside": True, "has_walls": True},
            {**_VALID, "in_a_room": True, "embed_in": "hall"},
            {**_VALID, "embed_in": "hall"},
            {**_VALID, "in_a_room": True, "embed_in": "hall", "embed_at": "north_east"},
            {**_VALID, "embed_at": "center"},
        ):
            with self.subTest(wire=wire):
                StaircaseSpec.model_validate(wire)

    def test_size_forms(self):
        preset = StaircaseSpec.model_validate(
            {**_VALID, "size": {"size_type": "sq_small"}})
        self.assertEqual(preset.size.size_type, "sq_small")
        explicit = StaircaseSpec.model_validate(
            {**_VALID, "size": {"width_range": [4, 4], "depth_range": [5, 5]}})
        self.assertEqual(explicit.size.width_range, [4, 4])
        self.assertEqual(explicit.size.depth_range, [5, 5])
        no_depth = StaircaseSpec.model_validate(
            {**_VALID, "size": {"width_range": [4, 6]}})
        self.assertIsNone(no_depth.size.depth_range)

    def test_full_wire_roundtrip_and_immutability(self):
        wire = dict(stops=["a", "b"], staircase_id="s", staircase_type="spiral",
                    step_material="oak", size={"size_type": "spiral_3"},
                    facing="east", has_walls=True, outside=True,
                    is_movable=False, has_trapdoor=False, near_wall=False,
                    open_wall_shaft=None, closed_exit=False)
        spec = StaircaseSpec.model_validate(wire)
        dumped = spec.model_dump(mode="json")
        for key, value in wire.items():
            if key == "size":
                self.assertEqual(spec.size.model_dump(mode="json", exclude_none=True), value)
            else:
                self.assertEqual(dumped[key], value, key)
        with self.assertRaises(ValidationError):
            spec.stops = ["x", "y"]

    def test_structure_validates_staircases_without_changing_wire(self):
        wire = {
            "system_name": _UID,
            "display_name": "Test",
            "staircases": [dict(_VALID)],
        }
        original = deepcopy(wire)
        structure = StructureTemplate.model_validate(wire)
        self.assertEqual(wire, original)
        self.assertEqual(structure.staircases, wire["staircases"])

        wire["staircases"] = [{"stops": ["a", "b"], "staircase_type": "bogus"}]
        with self.assertRaises(ValidationError) as error:
            StructureTemplate.model_validate(wire)
        self.assertIn("staircases[0]", str(error.exception))

    def test_runtime_boundary_raises_generation_error(self):
        template = StructureTemplate.model_construct(
            system_name=_UID, display_name="Test",
            staircases=[{"staircase_type": "bogus"}],
        )
        with self.assertRaises(GenerationError) as error:
            StructureGeneratorService._resolve_staircases(template)
        self.assertIn("staircases[0]", str(error.exception))
        self.assertIn(_UID, str(error.exception))

    def test_runtime_boundary_returns_typed_list(self):
        wire = {"system_name": _UID, "display_name": "Test",
                "staircases": [dict(_VALID),
                               {**_VALID, "staircase_type": "vertical_ladder",
                                "staircase_id": "cellar_ladder"}]}
        template = StructureTemplate.model_validate(wire)
        resolved = StructureGeneratorService._resolve_staircases(template)
        self.assertTrue(all(isinstance(s, StaircaseSpec) for s in resolved))
        self.assertIs(resolved[0].staircase_type, StaircaseType.U_SHAPE)
        self.assertEqual(resolved[0].staircase_id, "staircase_hall_corridor")
        self.assertIs(resolved[1].staircase_type, StaircaseType.VERTICAL_LADDER)
        self.assertEqual(resolved[1].staircase_id, "cellar_ladder")

    def test_all_stdlib_structures_validate(self):
        from app.application.worldData.libraryPacks.manifest import PACK_MANIFEST_FILENAME
        root = Path(__file__).resolve().parents[2] / "structures_templates/base"
        paths = [p for p in root.glob("*.json") if p.name != PACK_MANIFEST_FILENAME]
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.name):
                StructureTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))


class ShaftSizeTests(unittest.TestCase):
    def test_rejects_empty_and_mixed_forms(self):
        for wire in ({}, {"size_type": "sq_small", "depth_range": [5, 5]},
                     {"depth_range": [5, 5]}):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                ShaftSize.model_validate(wire)
        ShaftSize.model_validate({"size_type": "sq_small"})
        ShaftSize.model_validate({"width_range": [3, 4]})


if __name__ == "__main__":
    unittest.main()
