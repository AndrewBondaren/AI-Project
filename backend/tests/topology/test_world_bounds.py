"""Unit tests — WorldBounds POJO + grid_bbox_from_locations."""

from __future__ import annotations

import unittest
from collections import UserList
from types import SimpleNamespace
from unittest.mock import patch

from app.application.worldData.generators.terrain.passes import bbox as bbox_module
from app.dataModel.topology.worldBounds import WorldBounds
from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.planning.composition.surfacePlanningEntry import surface_world_topology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class TestLocationsSequence(unittest.TestCase):
    def setUp(self):
        self.world = World(world_uid="sequence-world", name="Sequence", created_at="",
            fine_cells_per_map_cell=1000, grid_bbox_padding=2)
        self.rows = [NamedLocation(location_uid=uid, world_uid=self.world.world_uid,
            display_name=uid, created_at="", system_location_type="settlement",
            map_x=x, map_y=y, is_mobile=mobile)
            for uid, x, y, mobile in (("a", 0, 0, False), ("b", 3000, -1000, False),
                                     ("moving", 100000, 100000, True), ("unset", None, None, False))]

    def test_sequences_preserve_input_and_resolve_static_anchor_bounds(self):
        expected = WorldBounds(x_min=-2, x_max=5, y_min=-3, y_max=2)
        for locations in (self.rows, tuple(self.rows), UserList(self.rows)):
            with self.subTest(collection=type(locations).__name__):
                before = tuple(locations)
                anchors = static_map_anchors(locations)
                self.assertIsInstance(anchors, list)
                self.assertEqual(anchors, self.rows[:2])
                self.assertEqual(bbox_module.world_bounds_from_world(self.world, locations), expected)
                bbox = bbox_module.grid_bbox_from_locations(self.world, locations)
                self.assertEqual((bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max), (-2, 5, -3, 2))
                self.assertEqual(surface_world_topology(self.world, locations).bounds, expected)
                self.assertEqual(tuple(locations), before)

    def test_empty_sequences_and_declared_bounds_priority(self):
        for locations in ([], (), UserList()):
            with self.subTest(collection=type(locations).__name__):
                self.assertEqual(static_map_anchors(locations), [])
                self.assertIsNone(bbox_module.grid_bbox_from_locations(self.world, locations))
                self.assertIsNone(bbox_module.world_bounds_from_world(self.world, locations))
                with self.assertRaisesRegex(ValueError, "requires world bounds"):
                    surface_world_topology(self.world, locations)
        self.assertIsNone(bbox_module.world_bounds_from_world(self.world))
        declared = WorldBounds(x_min=10, x_max=11, y_min=20, y_max=21)
        self.world.world_bounds = declared.model_dump()
        for locations in ([], (), tuple(self.rows), UserList(self.rows)):
            with self.subTest(declared=True, collection=type(locations).__name__):
                self.assertEqual(bbox_module.world_bounds_from_world(self.world, locations), declared)
                bbox = bbox_module.grid_bbox_from_locations(self.world, locations)
                self.assertEqual((bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max), (10, 11, 20, 21))
                self.assertEqual(surface_world_topology(self.world, locations).bounds, declared)


class TestWorldBounds(unittest.TestCase):
    def test_try_parse_valid(self):
        b = WorldBounds.try_parse({"x_min": -2, "x_max": 2, "y_min": -1, "y_max": 3})
        self.assertIsNotNone(b)
        assert b is not None
        self.assertEqual(b.x_min, -2)
        self.assertEqual(b.y_max, 3)

    def test_try_parse_rejects_unordered(self):
        self.assertIsNone(WorldBounds.try_parse({"x_min": 5, "x_max": 1, "y_min": 0, "y_max": 1}))

    def test_try_parse_rejects_incomplete(self):
        self.assertIsNone(WorldBounds.try_parse({"x_min": 0, "x_max": 1}))
        self.assertIsNone(WorldBounds.try_parse(None))
        self.assertIsNone(WorldBounds.try_parse("nope"))


class TestGridBboxFromLocations(unittest.TestCase):
    def test_declared_bounds_win(self):
        from app.application.worldData.generators.terrain.passes.bbox import (
            grid_bbox_from_locations,
        )

        world = SimpleNamespace(
            world_bounds={"x_min": 1, "x_max": 3, "y_min": 2, "y_max": 4},
            grid_bbox_padding=2,
            fine_cells_per_map_cell=3000,
            map_settings=None,
        )
        bbox = grid_bbox_from_locations(world, [])
        self.assertIsNotNone(bbox)
        assert bbox is not None
        self.assertEqual((bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max), (1, 3, 2, 4))

    def test_anchor_fallback_with_padding(self):
        from app.application.worldData.generators.terrain.passes.bbox import (
            grid_bbox_from_locations,
        )

        world = SimpleNamespace(
            world_bounds=None,
            grid_bbox_padding=2,
            fine_cells_per_map_cell=3000,
            map_settings=None,
        )
        loc = SimpleNamespace(
            map_x=0, map_y=0, map_z=0, is_mobile=False,
        )
        with patch(
            bbox_module.__name__ + ".static_map_anchors",
            return_value=[loc],
        ), patch(
            bbox_module.__name__ + ".map_cell_fine_span",
            return_value=3000,
        ):
            bbox = grid_bbox_from_locations(world, [loc])
        self.assertIsNotNone(bbox)
        assert bbox is not None
        self.assertEqual(bbox.x_min, -2)
        self.assertEqual(bbox.x_max, 2)

    def test_world_bounds_from_world_declared(self) -> None:
        from app.application.worldData.generators.terrain.passes.bbox import (
            world_bounds_from_world,
        )

        world = SimpleNamespace(
            world_bounds={"x_min": 1, "x_max": 3, "y_min": 2, "y_max": 4},
        )
        bounds = world_bounds_from_world(world, [])
        self.assertIsNotNone(bounds)
        assert bounds is not None
        self.assertEqual((bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max), (1, 3, 2, 4))


class TestWorldBoundsNeighbors(unittest.TestCase):
    def test_grid_neighbor_inside_not_wrap(self) -> None:
        from app.dataModel.spatial.facing import Facing

        b = WorldBounds(x_min=0, x_max=2, y_min=0, y_max=2)
        self.assertEqual(b.grid_neighbor(1, 1, Facing.EAST), (2, 1))
        self.assertIsNone(b.grid_neighbor(2, 1, Facing.EAST))
        self.assertIsNone(b.antagonist_tile(1, 1, Facing.EAST))

    def test_antagonist_on_aabb_rim(self) -> None:
        from app.dataModel.spatial.facing import Facing

        b = WorldBounds(x_min=-1, x_max=1, y_min=0, y_max=2)
        self.assertEqual(b.antagonist_tile(1, 0, Facing.EAST), (-1, 0))
        self.assertEqual(b.antagonist_tile(-1, 0, Facing.WEST), (1, 0))
        self.assertEqual(b.antagonist_tile(0, 2, Facing.NORTH), (0, 0))
        self.assertEqual(b.antagonist_tile(0, 0, Facing.SOUTH), (0, 2))
        self.assertIsNone(b.grid_neighbor(1, 0, Facing.EAST))

    def test_wrap_owner_is_lexicographic_min(self) -> None:
        from app.dataModel.spatial.facing import Facing

        b = WorldBounds(x_min=-1, x_max=1, y_min=0, y_max=2)
        pair = b.wrap_owner_and_other(1, 0, Facing.EAST)
        self.assertEqual(pair, ((-1, 0), (1, 0)))
        assert pair is not None
        owner, other = pair
        self.assertEqual(b.facing_to_antagonist(owner, other), Facing.WEST)
        self.assertIsNone(b.wrap_owner_and_other(0, 1, Facing.EAST))

    def test_wrap_owner_skips_one_tile_wide(self) -> None:
        from app.dataModel.spatial.facing import Facing

        b = WorldBounds(x_min=3, x_max=3, y_min=0, y_max=0)
        self.assertEqual(b.antagonist_tile(3, 0, Facing.WEST), (3, 0))
        self.assertIsNone(b.wrap_owner_and_other(3, 0, Facing.WEST))


if __name__ == "__main__":
    unittest.main()
