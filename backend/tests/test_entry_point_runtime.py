"""Typed entry boundary, perimeter requirement and explicit door height."""
import unittest
from random import Random
from unittest.mock import patch
from pydantic import ValidationError

from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.room.roomFactory import instantiate_level_rooms
from app.application.worldData.generators.structure.passages.entry import _build_entry_point, _resolve_entry_height
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.room.entryPoint import EntryPoint
from app.db.models.locationLevel import LocationLevel
from tests.test_structure_orientation import simple_structure, test_world_building
from tests.test_u_shape_orientation_baseline import room


class EntryPointRuntimeTests(unittest.TestCase):
    def test_template_height_settings_bounds(self):
        wire = simple_structure().model_dump(mode="json")
        for field, value in (("door_height_ratio", 0), ("door_height_ratio", -1),
                             ("door_height_ratio", 1.01), ("door_height_max", 0)):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                StructureTemplate.model_validate({**wire, field: value})
        template = StructureTemplate.model_validate({**wire, "door_height_ratio": 1, "door_height_max": 1})
        self.assertEqual(template.door_height_ratio, 1)
        self.assertEqual(template.door_height_max, 1)

    def test_auto_height_table_and_overrides(self):
        instance = room()
        ep = EntryPoint(wall="south", passage_type="main_entrance")
        template = simple_structure()
        for z, expected in ((3, 2), (4, 3), (6, 4), (7, 5), (10, 5)):
            instance.z_height = z
            with self.subTest(z=z):
                self.assertEqual(_resolve_entry_height(instance, ep, 2, template), expected)
        instance.z_height = 10
        custom = template.model_copy(update={"door_height_ratio": 0.4, "door_height_max": 3})
        self.assertEqual(_resolve_entry_height(instance, ep, 2, custom), 3)
        self.assertEqual(_resolve_entry_height(instance, ep, 4, custom), 4)
        explicit = ep.model_copy(update={"door_height": 7})
        self.assertEqual(_resolve_entry_height(instance, explicit, 2, custom), 7)
        self.assertEqual(_resolve_entry_height(instance, ep.model_copy(update={"door_height": 1}), 3, custom), 3)

    def test_height_at_or_above_ceiling_fails_with_context(self):
        instance = room()
        template = simple_structure()
        for z, height in ((2, None), (4, 4), (4, 5)):
            instance.z_height = z
            ep = EntryPoint(wall="south", passage_type="main_entrance", door_height=height)
            with self.subTest(z=z, height=height), self.assertRaises(GenerationError) as error:
                _resolve_entry_height(instance, ep, 2, template)
            self.assertIn(instance.room_id, str(error.exception))
            self.assertIn(str(template.system_name), str(error.exception))

    def test_generation_passes_template_to_both_entrances(self):
        template = simple_structure().model_copy(update={"door_height_ratio": 0.5, "door_height_max": 3})
        definition = template.levels[0]["rooms"][0]
        definition["size"]["z_range"] = [8, 8]
        template.levels[0]["z_height"] = 8
        definition["back_entry_point"] = {"wall": "west", "passage_type": "service_entrance"}
        world, building = test_world_building()
        with patch("app.application.worldData.generators.structure.passages.entry._resolve_entry_height", wraps=_resolve_entry_height) as resolve:
            StructureGeneratorService().generate_from_template(world, building, template)
        self.assertEqual(resolve.call_count, 2)
        for call in resolve.call_args_list:
            self.assertIs(call.args[3], template)
            self.assertEqual(call.args[0].z_height, 8)

    def instantiate(self, template):
        world, _ = test_world_building()
        level = StructureGeneratorService._resolve_levels(template)[0]
        return instantiate_level_rooms(level, template, 5, 0, world, Random(42))

    def test_both_entries_are_typed_and_force_boolean_perimeter(self):
        for field in ("entry_point", "back_entry_point"):
            template = simple_structure()
            definition = template.levels[0]["rooms"][0]
            entry = definition.pop("entry_point")
            definition[field] = entry
            definition["perimeter_required"] = False
            instance = self.instantiate(template)[0]
            self.assertIsInstance(getattr(instance, field), EntryPoint)
            self.assertIs(instance.perimeter_required, True)
            self.assertIsInstance(definition[field], dict)
            definition.pop(field)
            self.assertIs(self.instantiate(template)[0].perimeter_required, False)
            definition["perimeter_required"] = True
            self.assertIs(self.instantiate(template)[0].perimeter_required, True)

    def test_invalid_runtime_entry_becomes_generation_error(self):
        template = simple_structure()
        for field in ("entry_point", "back_entry_point"):
            definition = template.levels[0]["rooms"][0]
            definition.pop("entry_point", None)
            definition[field] = {}
            with self.assertRaises(GenerationError) as error:
                self.instantiate(template)
            self.assertIn("hall", str(error.exception))
            self.assertIn(field, str(error.exception))

    def test_door_height_width_material_and_service_type_reach_builder(self):
        instance = room()
        instance.z_height = 8
        level = LocationLevel("level", "building", 0, 8, "Ground")
        for height, expected in ((None, 5), (1, 5), (4, 4)):
            for material in (None, "stone"):
                entry = EntryPoint(wall="east", passage_type="service_entrance",
                                   width=2, door_height=height, frame_material=material)
                with patch("app.application.worldData.generators.structure.passages.entry._exterior_cells_on_wall", return_value=[(1, 2), (1, 3)]), patch(
                    "app.application.worldData.generators.structure.passages.entry.DoorPlacer"
                ) as placer_class:
                    placer = placer_class.return_value
                    placer.filter_passable_from_center.return_value = [(1, 2), (1, 3)]
                    placer.place.return_value = True
                    passage = _build_entry_point(instance, entry, level, set(), {}, "world", "building", 2)
                self.assertEqual(passage.system_transition_type, entry.passage_type)
                self.assertEqual(placer.place.call_count, 2)
                for call in placer.place.call_args_list:
                    self.assertEqual(call.kwargs["height"], expected)
                    self.assertEqual(call.kwargs["facing"], entry.wall)
                    self.assertEqual(call.kwargs["mat"], material or instance.wall_material)
