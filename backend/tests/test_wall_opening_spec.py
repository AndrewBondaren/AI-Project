"""Wall-opening wire fallbacks and authored runtime overrides."""
import json
import tempfile
from app.application.worldData.generators.structure.errors import GenerationError
import unittest
from copy import deepcopy
from random import Random
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.core.generationLogging import generation_world_log
from app.dataModel.locations.structure.room.wallOpeningSpec import WallOpeningSpec
from app.dataModel.locations.structure.enums.buildingElement import StructureElement, WALL_OPENING_ELEMENTS
from app.application.worldData.generators.structure.cellFactory import _opening_cell
from app.application.worldData.generators.structure.passages.wallOpening import place_wall_openings
from app.application.worldData.generators.structure.passages.wallOpeningResolver import compute_exterior_wall_profiles
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell
from tests.test_structure_orientation import simple_structure, test_world_building
from tests.test_u_shape_orientation_baseline import room

FACTORY_LOGGER = "app.application.worldData.generators.structure.room.roomFactory"
OPENING_LOGGER = "app.application.worldData.generators.structure.passages.wallOpening"


class WallOpeningSpecTests(unittest.TestCase):
    def test_defaults_frozen_extra_and_roundtrip(self):
        spec = WallOpeningSpec()
        self.assertEqual(spec.model_dump(), dict(opening_type=None, frame_material=None,
                                                glass_material=None, window_z=None))
        self.assertFalse(spec.substitutions)
        self.assertEqual(WallOpeningSpec.model_validate(spec.model_dump()), spec)
        with self.assertRaises(ValidationError):
            WallOpeningSpec(placement="edges")
        with self.assertRaises(ValidationError):
            spec.window_z = 2
        for element in WALL_OPENING_ELEMENTS:
            self.assertIs(WallOpeningSpec(opening_type=element.value).opening_type, element)

    def test_invalid_parameters_reject_without_mutating_wire(self):
        for name, values in dict(opening_type=["door", "bad", [], 7],
                                 window_z=[-1, "bad", 1.5, True, "2"],
                                 frame_material=[[], 7, ""], glass_material=[{}, ""]).items():
            for value in values:
                with self.subTest(name=name, value=value):
                    wire = {name: value}
                    original = deepcopy(wire)
                    with self.assertRaises(ValidationError):
                        WallOpeningSpec.model_validate(wire)
                    self.assertEqual(wire, original)

    def generate(self, specs):
        world, building = test_world_building()
        template = simple_structure()
        template.levels[0]["rooms"][0]["wall_openings"] = specs
        before = deepcopy(template.model_dump())
        layout = StructureGeneratorService().generate_from_template(world, building, template)
        self.assertEqual(template.model_dump(), before)
        return layout

    def test_invalid_opening_stops_generation_with_warning(self):
        with self.assertLogs("app.application.jsonValidation.resolve", "WARNING") as logs:
            with self.assertRaises(GenerationError):
                self.generate([dict(opening_type="door", window_z=-1, glass_material=[])])
        self.assertTrue(any("WarningError" in line for line in logs.output))

    def test_empty_spec_is_quiet_and_identical_to_auto(self):
        with self.assertNoLogs(level="ERROR"):
            before, after = self.generate([]), self.generate([{}])
            self.assertEqual((before.cells, before.transitions), (after.cells, after.transitions))

    def test_multiple_specs_first_applies_and_extra_is_logged(self):
        first = dict(opening_type="vent", frame_material="frame", glass_material="mesh", window_z=0)
        expected = self.generate([first])
        with self.assertLogs(FACTORY_LOGGER, level="ERROR") as captured:
            actual = self.generate([first, dict(opening_type="porthole")])
        self.assertEqual((actual.cells, actual.transitions), (expected.cells, expected.transitions))
        self.assertEqual(len(captured.records), 1)
        self.assertIn("ignored", captured.output[0])

    def place(self, spec, height=5, base=10, ground=0, shaft=False, profile_height=None):
        r = room(width=7, depth=7)
        r.z_height = height
        r.is_shaft = shaft
        r.wall_openings = [WallOpeningSpec.model_validate(spec)]
        world, _ = test_world_building()
        cells = {(x, y, z): MapCell(world.world_uid, x, y, z,
                                   system_building_element=StructureElement.WALL)
                 for x, y in r.get_footprint() for z in range(base, base + height)}
        level = LocationLevel(level_uid="level", location_uid="building",
                              z=base, z_height=height, display_name="Test")
        profiles = compute_exterior_wall_profiles([r], r.get_footprint(), base)
        if profile_height is not None:
            profiles[r.uid_key].z_height = profile_height
        with patch(OPENING_LOGGER + "._opening_cell", wraps=_opening_cell) as opening, \
             patch(OPENING_LOGGER + ".compute_exterior_wall_profiles", return_value=profiles):
            place_wall_openings([r], r.get_footprint(), cells, level, world, "building", Random(1), ground)
        return cells, opening.call_args_list

    def test_overrides_reach_opening_cell_for_every_element(self):
        for element in WALL_OPENING_ELEMENTS:
            with self.subTest(element=element):
                cells, calls = self.place(dict(opening_type=element.value, frame_material="frame",
                                              glass_material="glass", window_z=0))
                self.assertTrue(calls)
                for call in calls:
                    self.assertIn(call.args[2], (10, 11))
                    self.assertEqual(call.args[5:7], (element.value, "frame"))
                    self.assertEqual(call.kwargs["glass_material"], "glass")
                self.assertEqual({c.args[2] for c in calls}, {10, 11})

    def test_z_bounds_fallback_and_last_fitting_start(self):
        for bad in (4, 5, 20):
            with self.subTest(bad=bad), self.assertLogs(OPENING_LOGGER, level="ERROR") as captured:
                _, calls = self.place(dict(window_z=bad))
            self.assertEqual(len(captured.records), 1)
            self.assertEqual({c.args[2] for c in calls}, {11, 12})
        with self.assertNoLogs(OPENING_LOGGER, level="ERROR"):
            _, calls = self.place(dict(window_z=3))
        self.assertEqual({c.args[2] for c in calls}, {13, 14})

    def test_reduced_profile_uses_same_height_for_geometry_and_override_bounds(self):
        with self.assertLogs(OPENING_LOGGER, level="ERROR") as captured:
            _, calls = self.place(dict(window_z=5), height=10, profile_height=5)
        self.assertEqual(len(captured.records), 1)
        self.assertIn("z_height=5", captured.output[0])
        self.assertEqual({c.args[2] for c in calls}, {11, 12})
        with self.assertNoLogs(OPENING_LOGGER, level="ERROR"):
            _, calls = self.place(dict(window_z=3), height=10, profile_height=5)
        self.assertEqual({c.args[2] for c in calls}, {13, 14})

    def test_taller_profile_cannot_raise_room_ceiling(self):
        with self.assertLogs(OPENING_LOGGER, level="ERROR"):
            _, calls = self.place(dict(window_z=4), height=5, profile_height=10)
        self.assertEqual({c.args[2] for c in calls}, {11, 12})
        with self.assertNoLogs(OPENING_LOGGER, level="ERROR"):
            _, calls = self.place({}, height=5, profile_height=10)
        self.assertEqual({c.args[2] for c in calls}, {11, 12})

    def test_underground_skip(self):
        cells, calls = self.place(dict(opening_type="vent", window_z=0), base=3, ground=4)
        self.assertFalse(calls)
        self.assertTrue(all(c.system_building_element == StructureElement.WALL for c in cells.values()))

    def test_authored_generation_is_deterministic_and_template_immutable(self):
        specs = [dict(opening_type="arrow_slit", frame_material="frame", window_z=0)]
        first = self.generate(specs)
        second = self.generate(specs)
        self.assertEqual((first.cells, first.transitions), (second.cells, second.transitions))
        openings = [c for c in first.cells if c.system_building_element == StructureElement.ARROW_SLIT]
        self.assertTrue(openings)
        self.assertTrue(all(c.system_material == "frame" and c.glass_material is None for c in openings))


if __name__ == "__main__":
    unittest.main()
