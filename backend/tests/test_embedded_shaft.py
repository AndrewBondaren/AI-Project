"""Embedded shaft geometry, fallback, entrance arch and runtime integration."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from app.application.worldData.generators.structure.staircase.shaftPlacer import (
    EmbeddedShaftPlacer, AdjacentShaftPlacer, make_shaft_placer,
)
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.application.worldData.generators.structure.cellBuilder import _interior, pass3_interior_walls
from app.application.worldData.generators.structure.passages.archway import _build_archway
from app.dataModel.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.dataModel.structure.enums.buildingElement import StructureElement
from app.dataModel.spatial.facing import Facing, INTERCARDINAL_FACINGS, CARDINAL_FACINGS
from app.utils.deterministicIds import scoped_rng, det_uuid
from tests.structureWire import room_wire, level_wire
from tests.test_structure_orientation import test_world_building
from tests.test_u_shape_orientation_baseline import room

PLACER = "app.application.worldData.generators.structure.staircase.shaftPlacer"
BUILDER = "app.application.worldData.generators.structure.passages.builder"


class EmbeddedShaftTests(unittest.TestCase):
    def scenario(self, at="north_east", embed_in="host", width=15, depth=13):
        host = room("host", x=10, y=20, width=width, depth=depth)
        shaft = room("shaft", x=None, y=None, width=5, depth=5)
        shaft.is_shaft = True
        shaft.staircase_id = "stairs"
        spec = StaircaseSpec(staircase_id="stairs", stops=["host", "upper"],
                            in_a_room=True, embed_in=embed_in, embed_at=at)
        return host, shaft, spec

    def test_four_corners_fit_merge_two_walls_and_face_host_interior(self):
        origins = {Facing.NORTHEAST: (20, 28), Facing.NORTHWEST: (10, 28),
                   Facing.SOUTHEAST: (20, 20), Facing.SOUTHWEST: (10, 20)}
        for corner, origin in origins.items():
            with self.subTest(corner=corner):
                host, shaft, spec = self.scenario(corner.value)
                self.assertTrue(make_shaft_placer(spec, building_uid="building").place(shaft, host, [host]))
                self.assertEqual((shaft.origin_x, shaft.origin_y), origin)
                self.assertLessEqual(shaft.get_footprint(), host.get_footprint())
                shared_wall = (shaft.get_footprint() - _interior(shaft.get_footprint())) & (
                    host.get_footprint() - _interior(host.get_footprint()))
                self.assertEqual(len(shared_wall), 9)
                walls = pass3_interior_walls([host, shaft], [], 0, "world", "building", "stone")
                self.assertEqual(len(walls), len({(c.x, c.y) for c in walls}))
                self.assertEqual(shaft.embedded_host_key, host.uid_key)
                inward = {Facing.SOUTH, Facing.WEST} if corner == Facing.NORTHEAST else (
                    {Facing.SOUTH, Facing.EAST} if corner == Facing.NORTHWEST else (
                    {Facing.NORTH, Facing.WEST} if corner == Facing.SOUTHEAST else {Facing.NORTH, Facing.EAST}))
                self.assertIn(shaft.embedded_entry, inward)

    def test_center_entirely_interior_with_four_separate_walls_and_keyed_entry(self):
        host, shaft, spec = self.scenario("center")
        self.assertTrue(EmbeddedShaftPlacer(spec, "building").place(shaft, host, [host]))
        self.assertEqual((shaft.origin_x, shaft.origin_y), (15, 24))
        self.assertLessEqual(shaft.get_footprint(), _interior(host.get_footprint()))
        expected = scoped_rng("building", "stairs", "embed_entry").choice(sorted(CARDINAL_FACINGS))
        self.assertEqual(shaft.embedded_entry, expected)
        walls = pass3_interior_walls([host, shaft], [], 0, "world", "building", "stone")
        positions = {(c.x, c.y) for c in walls}
        self.assertLessEqual(shaft.get_footprint() - _interior(shaft.get_footprint()), positions)

    def test_omitted_position_uses_stable_corner_order_and_scoped_rng(self):
        expected = scoped_rng("building", "stairs", "embed_at").choice(sorted(INTERCARDINAL_FACINGS))
        host, shaft, spec = self.scenario(None)
        other_host, other_shaft, other_spec = self.scenario(expected.value)
        EmbeddedShaftPlacer(spec, "building").place(shaft, host, [host])
        EmbeddedShaftPlacer(other_spec, "building").place(other_shaft, other_host, [other_host])
        self.assertEqual(shaft, other_shaft)

    def test_missing_unplaced_or_wrong_level_host_uses_largest_nonshaft_room(self):
        for embed_in in (None, "missing", "unplaced", "wrong_level"):
            with self.subTest(embed_in=embed_in):
                host, shaft, spec = self.scenario(embed_in=embed_in)
                small = room("small", x=-20, width=8, depth=8)
                unplaced = room("unplaced", x=None, y=None, width=30, depth=30)
                wrong_level = room("wrong_level", x=100, z=1, width=40, depth=40)
                with self.assertLogs(PLACER, "ERROR") as captured:
                    self.assertTrue(EmbeddedShaftPlacer(spec, "building").place(
                        shaft, small, [small, unplaced, wrong_level, host]))
                self.assertEqual(len(captured.records), 1)
                self.assertEqual(shaft.embedded_host_key, host.uid_key)

    def test_nonfit_or_overlap_logs_error_and_uses_adjacent_fallback(self):
        for overlap in (False, True):
            host, shaft, spec = self.scenario(width=15 if overlap else 5)
            rooms = [host]
            if overlap:
                blocker = room("blocker", x=20, y=28, width=3, depth=3)
                rooms.append(blocker)
            with self.assertLogs(PLACER, "ERROR"), patch.object(
                    AdjacentShaftPlacer, "place", return_value=True) as adjacent:
                self.assertTrue(EmbeddedShaftPlacer(spec, "building").place(shaft, host, rooms))
            adjacent.assert_called_once_with(shaft, host, rooms)
            self.assertIsNone(shaft.embedded_host_key)
            self.assertIsNone(shaft.embedded_entry)

    def test_tight_center_uses_real_adjacent_fallback(self):
        host, shaft, spec = self.scenario("center", width=7, depth=7)
        with self.assertLogs(PLACER, "ERROR") as captured:
            self.assertTrue(EmbeddedShaftPlacer(spec, "building").place(shaft, host, [host]))
        self.assertEqual(len(captured.records), 1)
        self.assertIsNone(shaft.embedded_host_key)
        self.assertFalse(_interior(shaft.get_footprint()) & _interior(host.get_footprint()))

    def test_service_propagates_embedded_origin_and_orientation_to_upper_shafts(self):
        host, shaft, spec = self.scenario()
        upper = room("upper", x=None, y=None, z=1, width=5, depth=5)
        upper.is_shaft = True
        upper.staircase_id = spec.staircase_id
        starts = {}
        StructureGeneratorService()._place_level_shafts(
            0, [spec], [host, shaft, upper], {"host": 0, "upper": 1},
            {spec.staircase_id: [shaft, upper]}, {"host": host}, starts, building_uid="building")
        self.assertTrue(upper.placed)
        self.assertEqual((upper.origin_x, upper.origin_y), (shaft.origin_x, shaft.origin_y))
        self.assertEqual(upper.facing, shaft.facing)
        self.assertEqual(starts[1], (shaft.origin_x, shaft.origin_y))

    def template(self, at, distinct_host=False):
        lower = room_wire(room_id="hall", size={"width_range": [18, 18], "depth_range": [18, 18]},
                          entry_point={"wall": "south", "passage_type": "main_entrance"})
        rooms = [lower]
        if distinct_host:
            rooms.append(room_wire(room_id="host", size={"width_range": [18, 18], "depth_range": [18, 18]}))
        return StructureTemplate(system_name="00000000-0000-4000-8000-000000000011",
            display_name="Embedded", default_z_height=6,
            levels=[level_wire(rooms=rooms), level_wire(z_offset=1, rooms=[room_wire(room_id="upper")])],
            staircases=[dict(staircase_id="stairs", staircase_type="u_shape", stops=["hall", "upper"],
                size={"width_range": [5, 5], "depth_range": [5, 5]}, has_walls=True,
                in_a_room=True, embed_in="host" if distinct_host else "hall", embed_at=at)])

    def test_generate_arch_targets_actual_host_only_on_entry_wall_and_propagates_origin(self):
        world, building = test_world_building()
        for at, distinct in (("north_east", False), ("north_west", False),
                             ("south_east", False), ("south_west", False),
                             ("center", True), (None, False)):
            with self.subTest(at=at, distinct=distinct):
                template = self.template(at, distinct)
                original = deepcopy(template.model_dump())
                captured = []
                def arch(*args, **kwargs):
                    if kwargs.get("shared_cells") is not None:
                        captured.append((args[0], args[1], args[2], list(kwargs["shared_cells"])))
                    return _build_archway(*args, **kwargs)
                with patch(BUILDER + "._build_archway", side_effect=arch):
                    first = StructureGeneratorService().generate_from_template(world, building, template)
                    second = StructureGeneratorService().generate_from_template(world, building, template)
                self.assertEqual(template.model_dump(), original)
                self.assertEqual((first.cells, first.passages), (second.cells, second.passages))
                self.assertEqual(len(captured), 2)
                conn, shaft, host, wall = captured[0]
                self.assertEqual(host.room_id, "host" if distinct else "hall")
                self.assertEqual(conn.to_room, host.room_id)
                self.assertEqual(len(wall), 3)
                self.assertTrue(len({x for x, y in wall}) == 1 or len({y for x, y in wall}) == 1)
                uid = det_uuid(building.location_uid, "arch", shaft.room_id, host.room_id)
                self.assertTrue(any(p.passage_uid == uid for p in first.passages))
