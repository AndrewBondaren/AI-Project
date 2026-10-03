"""Room/level wire boundaries, fallbacks, references and generation diagnostics."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from app.core.generationLogging import generation_world_log
from app.dataModel.annotationPolicy import field_policy, wire_enum_class, WireFieldPolicy
from app.dataModel.locations.structure.building.levelDef import LevelDef
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.attachWall import AttachWall
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.dataModel.locations.structure.room.sizeSpec import SizeSpec
from app.dataModel.locations.structure.room.entryPoint import EntryPoint
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from tests.structureWire import room_wire, level_wire
from tests.test_structure_orientation import simple_structure, test_world_building

LOGGER = "app.application.worldData.generators.structure.structureGeneratorService"
UID = "00000000-0000-4000-8000-000000000010"


def template_wire(*rooms):
    return dict(system_name=UID, display_name="Test", levels=[level_wire(rooms=list(rooms))])


class RoomDefTests(unittest.TestCase):
    def test_attach_wall_is_strict_enum_with_typed_fallback(self):
        annotation = RoomDef.__annotations__["attach_wall"]
        self.assertEqual(field_policy(annotation), WireFieldPolicy.STRICT_ON_WIRE)
        self.assertIs(wire_enum_class(annotation), AttachWall)
        for member in AttachWall:
            room = RoomDef.model_validate(room_wire(attach_to="host", attach_wall=member.value))
            self.assertIs(room.attach_wall, member)
            self.assertFalse(room.substitutions)
        for fields in ({}, {"attach_wall": None}, {"attach_wall": ""},
                       {"attach_wall": "bad"}, {"attach_wall": []}, {"attach_wall": 5}):
            with self.subTest(fields=fields):
                room = RoomDef.model_validate(room_wire(attach_to="host", **fields))
                self.assertIs(room.attach_wall, AttachWall.BOTH)
                self.assertEqual(len(room.substitutions), 1)
        self.assertFalse(RoomDef.model_validate(room_wire()).substitutions)

    def test_import_keeps_wire_and_runtime_logs_each_substitution_once(self):
        for fields in ({}, {"attach_wall": "invalid"}):
            wire = template_wire(room_wire(room_id="host"), room_wire(attach_to="host", **fields))
            original = deepcopy(wire)
            template = StructureTemplate.model_validate(wire)
            self.assertEqual(wire, original)
            self.assertEqual(template.levels, original["levels"])
            with self.assertLogs(LOGGER, level="ERROR") as captured:
                levels = StructureGeneratorService._resolve_levels(template, "building-test")
            self.assertEqual(len(captured.records), 1)
            self.assertIn("building-test", captured.output[0])
            self.assertIn("hall", captured.output[0])
            self.assertIn("both", captured.output[0])
            self.assertIs(levels[0].rooms[1].attach_wall, AttachWall.BOTH)

    def test_substitution_reaches_central_generation_transcript(self):
        template = StructureTemplate.model_validate(template_wire(
            room_wire(room_id="host"), room_wire(attach_to="host", attach_wall="bad")))
        with tempfile.TemporaryDirectory() as directory:
            with generation_world_log("rooms-test", mode="test", root=directory) as path:
                StructureGeneratorService._resolve_levels(template, "building-test")
            records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
        errors = [record for record in records if record["level"] == "ERROR"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["logger"], LOGGER)
        self.assertIn("attach_wall", errors[0]["msg"])
        self.assertIn("both", errors[0]["msg"])

    def test_valid_and_inapplicable_defaults_are_quiet(self):
        template = StructureTemplate.model_validate(template_wire(
            room_wire(room_id="host"), room_wire(attach_to="host", attach_wall="both")))
        with self.assertNoLogs(LOGGER, level="WARNING"):
            StructureGeneratorService._resolve_levels(template)

    def test_size_forms_and_height_priority(self):
        preset = SizeSpec(size_type="big")
        self.assertEqual(preset.height_range(9, 7), [7, 7])
        explicit = SizeSpec(size_type="big", z_range=[5, 6])
        self.assertEqual(explicit.height_range(9, 7), [5, 6])
        raw = SizeSpec(width_range=[5, 6], depth_range=[3, 4])
        self.assertEqual(raw.height_range(9, None), [3, 3])
        for bad in ({}, {"size_type": "missing"}, {"size_type": "big", "width_range": [5, 5]},
                    {"width_range": [0, 3]}, {"width_range": [4, 3]}, {"width_range": [3]},
                    {"width_range": [3, 3], "z_range": [3, 2]}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                SizeSpec.model_validate(bad)

    def test_depth_is_required_only_for_shapes_that_use_it(self):
        for shape in ("square", "circle", "semicircle"):
            RoomDef.model_validate(room_wire(shape_type=shape, size={"width_range": [5, 5]}))
        for shape in ("rectangle", ["square", "rectangle"], None):
            with self.subTest(shape=shape), self.assertRaises(ValidationError):
                RoomDef.model_validate(room_wire(shape_type=shape, size={"width_range": [5, 5]}))

    def test_conditional_shape_params_for_every_array_member(self):
        for shape, fields in (("l_shape", {"arm_width_range": [2, 3], "arm_depth_range": [2, 3]}),
                              ("t_shape", {"stem_width_range": [2, 3]})):
            for selection in (shape, [shape], ["square", shape]):
                with self.subTest(selection=selection):
                    with self.assertRaises(ValidationError):
                        RoomDef.model_validate(room_wire(shape_type=selection))
                    room = RoomDef.model_validate(room_wire(shape_type=selection, shape_params=fields))
                    self.assertEqual(room.shape_params.arm_corner, "any")
                    self.assertEqual(room.shape_params.stem_wall, "any")
                    for field in fields:
                        with self.assertRaises(ValidationError):
                            RoomDef.model_validate(room_wire(shape_type=selection, shape_params={k: v for k, v in fields.items() if k != field}))

    def test_stem_width_must_be_strictly_less_than_minimum_beam_width(self):
        for width in ([2, 5], [5, 6]):
            with self.subTest(width=width), self.assertRaises(ValidationError):
                RoomDef.model_validate(room_wire(shape_type="t_shape", shape_params={"stem_width_range": width}))
        RoomDef.model_validate(room_wire(shape_type="t_shape", shape_params={"stem_width_range": [2, 4]}))

    def test_irrelevant_shape_params_are_accepted(self):
        room = RoomDef.model_validate(room_wire(shape_params={"stem_width_range": [8, 9]}))
        self.assertEqual(room.shape_params.stem_width_range, [8, 9])

    def test_required_fields_count_and_extra_keys(self):
        for name in ("room_id", "display_name", "room_type", "is_public", "is_forbidden", "required", "size"):
            wire = room_wire()
            wire.pop(name)
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RoomDef.model_validate(wire)
        self.assertEqual(RoomDef.model_validate(room_wire()).count, 1)
        RoomDef.model_validate(room_wire(required=False, count_range=[1, 2]))
        for fields in ({"unknown": True}, {"required": False}, {"count": 0},
                       {"count": 1, "count_range": [1, 2]}, {"required": False, "count_range": [0, 1]}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                RoomDef.model_validate(room_wire(**fields))

    def test_entry_reuse_frozen_models_and_wire_roundtrip(self):
        wire = room_wire(entry_point={"wall": "south", "passage_type": "main_entrance"}, purpose=None)
        parsed = RoomDef.model_validate(wire)
        self.assertIsInstance(parsed.entry_point, EntryPoint)
        replay = RoomDef.model_validate(parsed.model_dump(mode="json", exclude_unset=True))
        self.assertEqual(parsed, replay)
        for model, field, value in ((parsed, "room_id", "other"), (parsed.size, "size_type", "small"),
                                     (LevelDef.model_validate(level_wire()), "z_offset", 3)):
            with self.assertRaises(ValidationError):
                setattr(model, field, value)

    def test_import_rejects_duplicate_ids_and_missing_or_cross_level_hosts(self):
        for wire in (template_wire(room_wire(), room_wire()),
                     template_wire(room_wire(attach_to="missing")),
                     dict(system_name=UID, display_name="Test", levels=[
                         level_wire(rooms=[room_wire(attach_to="host")]),
                         level_wire(z_offset=1, rooms=[room_wire(room_id="host")])])):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                StructureTemplate.model_validate(wire)

    def test_runtime_missing_host_skips_room_and_dependents(self):
        template = StructureTemplate.model_validate(template_wire(
            room_wire(room_id="host"), room_wire(attach_to="host", attach_wall="both"),
            room_wire(room_id="child", attach_to="hall", attach_wall="both")))
        template.levels[0]["rooms"][1]["attach_to"] = "missing"
        with self.assertLogs(LOGGER, level="ERROR") as captured:
            levels = StructureGeneratorService._resolve_levels(template)
        self.assertEqual([room.room_id for room in levels[0].rooms], ["host"])
        self.assertEqual(len(captured.records), 2)

    def test_runtime_missing_required_field_raises_contextual_generation_error(self):
        template = StructureTemplate.model_validate(template_wire(room_wire()))
        template.levels[0]["rooms"][0].pop("size")
        with self.assertRaises(GenerationError) as error:
            StructureGeneratorService._resolve_levels(template, "building-test")
        for expected in (UID, "building-test", "hall", "size"):
            self.assertIn(expected, str(error.exception))

    def test_invalid_height_falls_back_with_error_but_omission_is_quiet(self):
        for value in (0, -1, "bad"):
            template = StructureTemplate.model_validate(template_wire(room_wire()))
            template.levels[0]["z_height"] = value
            with self.assertLogs(LOGGER, level="ERROR"):
                levels = StructureGeneratorService._resolve_levels(template)
            self.assertIsNone(levels[0].z_height)
        with self.assertNoLogs(LOGGER, level="WARNING"):
            StructureGeneratorService._resolve_levels(StructureTemplate.model_validate(template_wire(room_wire())))

    def test_generation_continues_after_broken_attachment(self):
        template = simple_structure()
        template.levels[0]["rooms"].append(room_wire(room_id="orphan", attach_to="absent", attach_wall="both"))
        world, building = test_world_building()
        with self.assertLogs(LOGGER, level="ERROR"):
            layout = StructureGeneratorService().generate_from_template(world, building, template)
        self.assertTrue(layout.cells)
        self.assertEqual(len(layout.rooms), 1)
