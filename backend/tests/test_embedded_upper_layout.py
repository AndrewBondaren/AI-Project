"""B1: exact source XY, no clipping fallback, diagnostic omission and upper exits."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from app.application.worldData.debugStructureRotations import RotationProbe
from app.application.worldData.generators.structure.staircase.embeddedUpperLayout import prepare_embedded_upper
from app.application.worldData.generators.structure.layoutEngine import layout_level
from app.application.worldData.generators.structure.cellBuilder import pass2_floors, _interior
from app.application.worldData.generators.structure.passages.corridorTrimmer import trim_corridor_rooms
from app.core.generationLogging import generation_world_log
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.structure.enums.buildingElement import StructureElement
from tests import test_embedded_shaft
from tests.test_structure_orientation import test_world_building
from tests.test_u_shape_orientation_baseline import room
from app.utils.deterministicIds import det_uuid

LOGGER = "app.application.worldData.generators.structure.staircase.embeddedUpperLayout"


class EmbeddedUpperLayoutTests(unittest.TestCase):
    def scenario(self, width=18, depth=18):
        lower = room("hall", x=10, y=20, width=18, depth=18)
        target = room("upper", x=None, y=None, z=1, width=width, depth=depth)
        shafts = [room("shaft_lo", x=23, y=33, width=5, depth=5),
                  room("shaft_hi", x=23, y=33, z=1, width=5, depth=5)]
        for shaft in shafts:
            shaft.is_shaft = True
            shaft.facing = Facing.NORTH
            shaft.staircase_id = "stairs"
        shafts[0].embedded_host_key = lower.uid_key
        shafts[0].embedded_entry = Facing.SOUTH
        spec = StaircaseSpec(staircase_id="stairs", stops=["hall", "upper"],
                             in_a_room=True, embed_in="hall")
        return lower, target, shafts, spec

    def prepare(self, lower, target, shafts, spec, extras=(), bounds=(10, 20, 27, 37)):
        rooms = [lower, target, *shafts, *extras]
        prepare_embedded_upper(1, rooms, [spec], {"stairs": shafts}, bounds, "building")
        layout_level([r for r in rooms if r.z_offset == 1], [], 90, 90, bounds,
                     staircases=[spec], building_uid="building")

    def test_host_is_fixed_above_source_and_not_repositioned_or_clipped(self):
        lower, target, shafts, spec = self.scenario()
        target.attach_to = "unrelated"
        self.prepare(lower, target, shafts, spec)
        self.assertEqual((target.origin_x, target.origin_y), (lower.origin_x, lower.origin_y))
        self.assertEqual((target.width, target.depth), (18, 18))
        self.assertEqual(shafts[1].embedded_host_key, target.uid_key)
        self.assertTrue(target.layout_locked)
        self.assertTrue(shafts[1].get_footprint() <= target.get_footprint())

    def test_upper_floor_is_cut_out_only_inside_shaft(self):
        lower, target, shafts, spec = self.scenario()
        self.prepare(lower, target, shafts, spec)
        floors = pass2_floors([target, shafts[1]], 6, "world", {target.uid_key: "upper-uid"})
        xy = {(c.x, c.y) for c in floors}
        self.assertEqual(xy, target.get_footprint() - shafts[1].get_footprint())

    def test_no_room_created_for_bounds_shaft_fit_or_exit_failure(self):
        for width, depth, reason in ((19, 18, "parent floor bounds"),
                                     (5, 5, "does not contain"),
                                     (18, 5, "does not contain")):
            with self.subTest(width=width, depth=depth):
                lower, target, shafts, spec = self.scenario(width, depth)
                with self.assertLogs(LOGGER, "ERROR") as logs:
                    self.prepare(lower, target, shafts, spec)
                self.assertEqual(len(logs.records), 1)
                self.assertIn(reason, logs.output[0])
                self.assertIn("staircase='stairs'", logs.output[0])
                self.assertIn("from_room='hall'", logs.output[0])
                self.assertIn("to_room='upper'", logs.output[0])
                self.assertFalse(target.placed)
                self.assertTrue(target.layout_excluded)
                self.assertFalse(shafts[1].placed)
                self.assertEqual((target.width, target.depth), (width, depth))

    def test_conflicting_shaft_excludes_target_instead_of_moving_it(self):
        lower, target, shafts, spec = self.scenario()
        other = room("other-shaft", x=15, y=25, z=1, width=5, depth=5)
        other.is_shaft = True
        with self.assertLogs(LOGGER, "ERROR") as logs:
            self.prepare(lower, target, shafts, spec, [other])
        self.assertIn("other-shaft_0", logs.output[0])
        self.assertFalse(target.placed)

    def test_missing_source_skips_target_and_logs_cause(self):
        lower, target, shafts, spec = self.scenario()
        lower.origin_x = lower.origin_y = None
        with self.assertLogs(LOGGER, "ERROR") as logs:
            self.prepare(lower, target, shafts, spec)
        self.assertIn("source room missing", logs.output[0])
        self.assertFalse(target.placed)

    def test_full_shaft_without_space_for_landing_is_rejected(self):
        lower, target, shafts, spec = self.scenario(5, 5)
        for shaft in shafts:
            shaft.origin_x, shaft.origin_y = lower.origin_x, lower.origin_y
        with self.assertLogs(LOGGER, "ERROR") as logs:
            self.prepare(lower, target, shafts, spec)
        self.assertIn("no interior floor", logs.output[0])
        self.assertFalse(target.placed)

    def test_locked_corridor_is_not_trimmed(self):
        lower, target, shafts, spec = self.scenario()
        target.room_type = "corridor"
        self.prepare(lower, target, shafts, spec)
        before = (target.origin_x, target.origin_y, target.width, target.depth)
        trim_corridor_rooms([lower, target, *shafts], [spec])
        self.assertEqual((target.origin_x, target.origin_y, target.width, target.depth), before)

    def test_three_floor_generation_aligns_each_stop(self):
        template = test_embedded_shaft.EmbeddedShaftTests().template("north_east")
        third = deepcopy(template.levels[1])
        third["z_offset"] = 2
        third["rooms"][0]["room_id"] = "top"
        template.levels.append(third)
        template.staircases[0]["stops"].append("top")
        world, building = test_world_building()
        probe = RotationProbe()
        result = probe.generate_from_template(world, building, template)
        stops = [next(r for r in probe.runtime_rooms if r.room_id == name)
                 for name in ("hall", "upper", "top")]
        self.assertTrue(all(r.placed for r in stops))
        self.assertEqual(len({(r.origin_x, r.origin_y) for r in stops}), 1)
        self.assertEqual(sum(p.system_passage_type == "staircase" for p in result.passages), 2)

    def test_cellar_to_ground_places_source_before_aligned_target(self):
        template = test_embedded_shaft.EmbeddedShaftTests().template("north_east")
        template.levels[0]["z_offset"] = -1
        template.levels[1]["z_offset"] = 0
        world, building = test_world_building()
        probe = RotationProbe()
        result = probe.generate_from_template(world, building, template)
        lower = next(r for r in probe.runtime_rooms if r.room_id == "hall")
        target = next(r for r in probe.runtime_rooms if r.room_id == "upper")
        self.assertTrue(target.placed)
        self.assertEqual((target.origin_x, target.origin_y), (lower.origin_x, lower.origin_y))
        self.assertTrue(any(p.system_passage_type == "staircase" for p in result.passages))

    def test_failed_middle_stop_prevents_later_stop_from_being_placed(self):
        lower, target, shafts, spec = self.scenario(5, 5)
        spec = spec.model_copy(update={"stops": ["hall", "upper", "top"]})
        top = room("top", x=None, y=None, z=2, width=18, depth=18)
        last_shaft = room("shaft_top", x=23, y=33, z=2, width=5, depth=5)
        last_shaft.is_shaft = True
        last_shaft.facing = Facing.NORTH
        shafts.append(last_shaft)
        rooms = [lower, target, top, *shafts]
        with self.assertLogs(LOGGER, "ERROR") as logs:
            prepare_embedded_upper(1, rooms, [spec], {"stairs": shafts}, None, "building")
            prepare_embedded_upper(2, rooms, [spec], {"stairs": shafts}, None, "building")
        self.assertEqual(len(logs.records), 2)
        self.assertIn("from_room='upper' to_room='top'", logs.output[1])
        self.assertFalse(top.placed)
        self.assertTrue(top.layout_excluded)
        self.assertFalse(last_shaft.placed)

    def test_successful_generation_has_walkable_upper_exit_and_is_deterministic(self):
        template = test_embedded_shaft.EmbeddedShaftTests().template("north_east")
        before = deepcopy(template.model_dump())
        world, building = test_world_building()
        runs = []
        for _ in range(2):
            probe = RotationProbe()
            result = probe.generate_from_template(world, building, template)
            runs.append((result.cells, result.passages))
            lower = next(r for r in probe.runtime_rooms if r.room_id == "hall")
            target = next(r for r in probe.runtime_rooms if r.room_id == "upper")
            shaft = next(r for r in probe.runtime_rooms if r.is_shaft and r.z_offset == 1)
            self.assertEqual((target.origin_x, target.origin_y), (lower.origin_x, lower.origin_y))
            landing = next(p for p in result.passages if p.system_passage_type == "staircase")
            upper_z = next(level.z for level in result.levels if level.level_uid == landing.to_level_uid)
            cell = next(c for c in result.cells if (c.x, c.y, c.z) == (landing.to_x, landing.to_y, upper_z))
            self.assertEqual(cell.system_building_element, StructureElement.FLOOR)
            self.assertIn((landing.to_x, landing.to_y), target.get_footprint())
            self.assertNotIn((landing.to_x, landing.to_y), _interior(shaft.get_footprint()))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(template.model_dump(), before)

    def test_failure_reaches_transcript_and_omits_target_from_result(self):
        template = test_embedded_shaft.EmbeddedShaftTests().template("north_east")
        template.levels[1]["rooms"][0]["size"] = {"width_range": [5, 5], "depth_range": [5, 5]}
        world, building = test_world_building()
        with tempfile.TemporaryDirectory() as directory:
            with generation_world_log("embedded-upper", mode="test", root=directory) as path:
                probe = RotationProbe()
                result = probe.generate_from_template(world, building, template)
            records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
        errors = [r for r in records if r["logger"] == LOGGER and r["level"] == "ERROR"]
        self.assertEqual(len(errors), 1)
        self.assertIn("target not created", errors[0]["msg"])
        self.assertFalse(next(r for r in probe.runtime_rooms if r.room_id == "upper").placed)
        self.assertFalse(any(p.system_passage_type == "staircase" for p in result.passages))
        self.assertFalse(any(r.location_uid == det_uuid(building.location_uid, "upper_0")
                             for r in result.rooms))
