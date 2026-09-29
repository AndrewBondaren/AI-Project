"""S1: characterize author-frame U stairs without adapting their builders."""
import unittest
from random import Random
from unittest.mock import Mock

from app.application.worldData.generators.structure.staircase.uShape.uShapeHelper import _compute_fr_anchor, _compute_u_params
from app.application.worldData.generators.structure.staircase.uShape.uShape import _build_u_shape
from app.application.worldData.generators.structure.staircase.shaftPlacer import AdjacentShaftPlacer, EdgeMountedShaftPlacer
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.dataModel.spatial.facing import Facing, CARDINAL_WALL_OUTWARD_DELTA
from app.db.models.mapCell import MapCell


def room(name="hall", x=10, y=20, width=7, depth=7, z=0):
    return _RoomInstance(name, 0, z, "rectangle", width, depth, 3, name, "common_hall", True, False, True, "stone", "wood", origin_x=x, origin_y=y)


class UShapeBaselineTests(unittest.TestCase):
    def test_both_corners_fallback_previous_and_direction(self):
        expected = {
            Facing.NORTH: [(10, 20), (12, 20)], Facing.SOUTH: [(10, 23), (12, 23)],
            Facing.EAST: [(10, 20), (10, 23)], Facing.WEST: [(12, 20), (12, 23)],
        }
        for facing, corners in expected.items():
            for index in (0, 1):
                with self.subTest(facing=facing, corner=index):
                    rng = Mock(spec=Random)
                    rng.choice.side_effect = lambda values: values[index]
                    anchor, far, turn = _compute_fr_anchor(10, 20, 3, 4, facing, rng=rng)
                    self.assertEqual(anchor, corners[index])
                    self.assertEqual(far, (22 - anchor[0], 43 - anchor[1]))
                    occupied = {(*anchor, 0): MapCell("w", *anchor, 0, system_building_element="wall")}
                    fallback = _compute_fr_anchor(10, 20, 3, 4, facing, cells=occupied, rng=rng)[0]
                    self.assertEqual(fallback, corners[1-index])
                    rng.reset_mock()
                    self.assertEqual(_compute_fr_anchor(10, 20, 3, 4, facing, prev_fr_anchor=anchor, rng=rng)[0], anchor)
                    rng.choice.assert_not_called()
                    self.assertEqual(abs(turn[0]) + abs(turn[1]), 1)

    def test_rectangular_single_and_multi_march_paths(self):
        for facing in Facing.NORTH, Facing.EAST, Facing.SOUTH, Facing.WEST:
            for height in (3, 16):
                for index in (0, 1):
                    with self.subTest(facing=facing, height=height, corner=index):
                        rng = Mock(spec=Random)
                        rng.choice.side_effect = lambda values: values[index]
                        params = _compute_u_params(10, 20, 3, 4, facing, height, rng=rng)
                        self.assertEqual(params.V_init, CARDINAL_WALL_OUTWARD_DELTA[facing])
                        self.assertEqual(params.march_count == 1, height == 3)
                        cells = {}
                        stairs, floors = _build_u_shape(params, 7, height, "w", "b", "stone", cells)
                        self.assertEqual(len(stairs), height)
                        self.assertEqual(sorted(z for _, _, z in stairs), list(range(7, 7+height)))
                        path = set(stairs + floors)
                        visited = {stairs[0]}
                        while True:
                            more = {p for p in path - visited if any(abs(p[0]-q[0])+abs(p[1]-q[1]) <= 1 and abs(p[2]-q[2]) <= 1 for q in visited)}
                            if not more:
                                break
                            visited |= more
                        self.assertEqual(visited, path)
                        self.assertTrue(all(c.system_facing is not None for c in cells.values()))

    @unittest.expectedFailure
    def test_known_rectangular_ns_height12_l_march_loses_two_steps(self):
        # Existing S1 defect: L-march emits two steps although march_steps requests three.
        params = _compute_u_params(10, 20, 3, 4, "north", 12, rng=Random(0))
        stairs, _ = _build_u_shape(params, 7, 12, "w", "b", "stone", {})
        self.assertEqual(len(stairs), 12)

    def test_adjacent_and_external_shaft_entry_side(self):
        for placer in (AdjacentShaftPlacer(), EdgeMountedShaftPlacer()):
            hall, shaft = room(), room("shaft", width=5, depth=6)
            shaft.origin_x = shaft.origin_y = None
            shaft.facing = Facing.NORTH
            self.assertTrue(placer.place(shaft, hall, [hall]))
            self.assertEqual(shaft.origin_y, hall.origin_y + hall.depth - 1)
            self.assertEqual(shaft.facing, Facing.NORTH)
