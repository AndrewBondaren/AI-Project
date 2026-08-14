"""Unit tests — WorldBounds POJO + grid_bbox_from_locations."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.dataModel.worldPack.worldBounds import WorldBounds


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
            map_cell_size_m=3000,
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
            map_cell_size_m=3000,
            map_settings=None,
        )
        loc = SimpleNamespace(
            map_x=0, map_y=0, map_z=0, is_mobile=False,
        )
        with patch(
            "app.application.worldData.generators.terrain.passes.bbox.static_map_anchors",
            return_value=[loc],
        ), patch(
            "app.application.worldData.generators.terrain.passes.bbox.cell_size_m",
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
