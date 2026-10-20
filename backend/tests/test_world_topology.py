"""Surface topology contract; legacy bounds lookups remain unchanged."""

import unittest

from pydantic import ValidationError

from app.dataModel.spatial.facing import CARDINAL_FACINGS, CARDINAL_WALL_OUTWARD_DELTA, NS_FACINGS, Facing, opposite
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import NeighborResult, WorldTopology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode


class WorldTopologyTests(unittest.TestCase):
    def setUp(self):
        self.bounds = WorldBounds(x_min=-2, x_max=1, y_min=3, y_max=5)
        self.planar = WorldTopology(mode=WorldTopologyMode.PLANAR, bounds=self.bounds)
        self.wrapped = WorldTopology(mode=WorldTopologyMode.WRAPPED, bounds=self.bounds)
        self.sphere = WorldTopology(mode=WorldTopologyMode.SPHERE, bounds=self.bounds)
        self.topologies = (self.planar, self.wrapped, self.sphere)

    def test_default_matches_scalar_and_legacy_wrapped_lookup(self):
        topology = WorldTopology(bounds=self.bounds)
        self.assertEqual(topology.mode, WorldTerrainScalars.canonical_defaults().world_topology_mode)
        self.assertIs(topology.mode, WorldTopologyMode.WRAPPED)
        for x, y, facing in self.bounds.edge_tiles():
            self.assertEqual(topology.grid_neighbor(x, y, facing), self.bounds.grid_neighbor(x, y, facing))
            self.assertEqual(topology.antagonist_tile(x, y, facing), self.bounds.antagonist_tile(x, y, facing))

    def test_every_wrapped_and_sphere_cell_has_four_reversible_neighbors(self):
        for topology in (self.wrapped, self.sphere):
            for x in range(self.bounds.x_min, self.bounds.x_max + 1):
                for y in range(self.bounds.y_min, self.bounds.y_max + 1):
                    results = [topology.neighbor(x, y, facing) for facing in CARDINAL_FACINGS]
                    self.assertEqual(sum(result is not None for result in results), 4)
                    for facing, result in zip(CARDINAL_FACINGS, results):
                        with self.subTest(mode=topology.mode, coord=(x, y), facing=facing):
                            self.assertIsInstance(result, NeighborResult)
                            self.assertTrue(topology.bounds.contains(*result.coord))
                            reverse = facing if result.invert_dy else opposite(facing)
                            self.assertEqual(topology.neighbor(*result.coord, reverse).coord, (x, y))
                            internal = self.bounds.grid_neighbor(x, y, facing)
                            self.assertEqual(result.edge_crossing, internal is None)
                            if internal is not None:
                                self.assertEqual(result.coord, internal)
                                self.assertFalse(result.invert_dy)

    def test_planar_edge_is_void_and_interior_is_ordinary_step(self):
        for x, y, facing in self.bounds.edge_tiles():
            self.assertIsNone(self.planar.neighbor(x, y, facing))
            self.assertIsNone(self.planar.antagonist_tile(x, y, facing))
        self.assertEqual(self.planar.neighbor(-1, 4, Facing.NORTH),
                         NeighborResult(coord=(-1, 5), edge_crossing=False, invert_dy=False))
        self.assertEqual(self.planar.seam_pairs(), ())

    def test_sphere_y_edges_use_same_row_half_turn_and_invert_only_dy(self):
        for y, facing in ((self.bounds.y_max, Facing.NORTH), (self.bounds.y_min, Facing.SOUTH)):
            result = self.sphere.neighbor(self.bounds.x_min, y, facing)
            self.assertEqual(result.coord, (0, y))
            self.assertTrue(result.edge_crossing)
            self.assertTrue(result.invert_dy)
        west = self.sphere.neighbor(self.bounds.x_min, 4, Facing.WEST)
        self.assertEqual(west.coord, (self.bounds.x_max, 4))
        self.assertTrue(west.edge_crossing)
        self.assertFalse(west.invert_dy)

    def test_canonicalize_agrees_with_neighbor_for_each_one_step_crossing(self):
        for topology in self.topologies:
            for x, y, facing in self.bounds.edge_tiles():
                dx, dy = CARDINAL_WALL_OUTWARD_DELTA[facing]
                result = topology.neighbor(x, y, facing)
                expected = result.coord if result is not None else None
                self.assertEqual(topology.canonicalize(x + dx, y + dy), expected)

    def test_canonicalize_multiple_periods_negative_origin_and_idempotence(self):
        cases = (
            ((-3, 4), (1, 4), (1, 4)),
            ((2, 4), (-2, 4), (-2, 4)),
            ((-2, 6), (-2, 3), (0, 5)),
            ((-2, 2), (-2, 5), (0, 3)),
            ((-2, 7), (-2, 4), (0, 4)),
            ((-2, 9), (-2, 3), (-2, 3)),
            ((-2, -1), (-2, 5), (-2, 5)),
        )
        for raw, wrapped, sphere in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.wrapped.canonicalize(*raw), wrapped)
                self.assertEqual(self.sphere.canonicalize(*raw), sphere)
                self.assertIsNone(self.planar.canonicalize(*raw))
        for topology in self.topologies:
            for x in range(-12, 12):
                for y in range(-8, 14):
                    canonical = topology.canonicalize(x, y)
                    if canonical is not None:
                        self.assertTrue(topology.bounds.contains(*canonical))
                        self.assertEqual(topology.canonicalize(*canonical), canonical)

    def test_sphere_odd_width_is_resolved_without_mutating_authored_bounds(self):
        authored = WorldBounds(x_min=5, x_max=7, y_min=-2, y_max=0)
        topology = WorldTopology(mode=WorldTopologyMode.SPHERE, bounds=authored)
        self.assertEqual(topology.bounds.x_max, 8)
        self.assertEqual(topology.bounds.width, 4)
        self.assertEqual(authored.x_max, 7)
        self.assertEqual(WorldTopology(bounds=authored).bounds, authored)
        self.assertEqual(WorldTopology(mode=WorldTopologyMode.PLANAR, bounds=authored).bounds, authored)

    def test_seam_pairs_provide_owner_and_both_faces_without_collapsing_edges(self):
        for topology in (self.wrapped, self.sphere):
            pairs = topology.seam_pairs()
            self.assertEqual(len(pairs), 7)
            self.assertEqual(pairs, topology.seam_pairs())
            self.assertEqual(len(set(pairs)), len(pairs))
            for pair in pairs:
                with self.subTest(mode=topology.mode, pair=pair):
                    self.assertLess(pair.owner, pair.other)
                    forward = topology.neighbor(*pair.owner, pair.owner_facing)
                    backward = topology.neighbor(*pair.other, pair.other_facing)
                    self.assertEqual(forward.coord, pair.other)
                    self.assertEqual(backward.coord, pair.owner)
                    self.assertTrue(forward.edge_crossing)
                    self.assertEqual(pair.invert_dy, forward.invert_dy)
                    if topology.mode is WorldTopologyMode.SPHERE and pair.owner_facing in NS_FACINGS:
                        self.assertEqual(pair.owner_facing, pair.other_facing)
                        self.assertTrue(pair.invert_dy)
                    else:
                        self.assertEqual(pair.other_facing, opposite(pair.owner_facing))
                        self.assertFalse(pair.invert_dy)

    def test_tiny_grids_keep_four_directions_and_distinct_polar_seams(self):
        one = WorldBounds(x_min=0, x_max=0, y_min=0, y_max=0)
        wrapped = WorldTopology(bounds=one)
        self.assertEqual(wrapped.seam_pairs(), ())
        for facing in CARDINAL_FACINGS:
            self.assertEqual(wrapped.neighbor(0, 0, facing).coord, (0, 0))
        sphere = WorldTopology(mode=WorldTopologyMode.SPHERE, bounds=one)
        pairs = sphere.seam_pairs()
        self.assertEqual(len(pairs), 3)
        polar_faces = {pair.owner_facing for pair in pairs if pair.invert_dy}
        self.assertEqual(polar_faces, NS_FACINGS)

    def test_invalid_mode_or_noncardinal_lookup_is_rejected(self):
        for mode in (None, "unknown"):
            with self.subTest(mode=mode), self.assertRaises(ValidationError):
                WorldTopology(mode=mode, bounds=self.bounds)
        with self.assertRaises(ValueError):
            self.sphere.neighbor(0, 4, Facing.NORTHEAST)
        self.assertIsNone(self.sphere.neighbor(100, 100, Facing.NORTH))
        self.assertEqual(self.wrapped.neighbor(-1, 5, Facing.NORTH.value),
                         self.wrapped.neighbor(-1, 5, Facing.NORTH))


if __name__ == "__main__":
    unittest.main()
