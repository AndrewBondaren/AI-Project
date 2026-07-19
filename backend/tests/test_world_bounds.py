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


if __name__ == "__main__":
    unittest.main()
