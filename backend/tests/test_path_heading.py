"""Tests for path heading corridor (DEBT-7)."""

import unittest
from types import SimpleNamespace

from app.application.worldData.pack.pathHeading import (
    filter_corridor_rects,
    heading_from_positions,
    macro_tiles_ahead,
    quantize_heading,
    resolve_path_heading,
)


class TestPathHeading(unittest.TestCase):

    def test_intent_overrides_history(self):
        heading = resolve_path_heading(
            intent_dx=0,
            intent_dy=1,
            positions=[(0, 0), (100, 0)],
        )
        assert heading is not None
        self.assertEqual((heading.dx, heading.dy), (0, 1))

    def test_history_fallback(self):
        heading = heading_from_positions([(10, 10), (50, 10), (90, 10)])
        assert heading is not None
        self.assertEqual((heading.dx, heading.dy), (1, 0))

    def test_no_heading_without_history(self):
        self.assertIsNone(resolve_path_heading(positions=[(1, 1)]))

    def test_macro_tiles_ahead_north(self):
        heading = quantize_heading(0, 10)
        assert heading is not None
        self.assertEqual(macro_tiles_ahead(2, 3, heading, 2), [(2, 4), (2, 5)])

    def test_filter_corridor_east(self):
        heading = quantize_heading(10, 0)
        assert heading is not None
        rects = [
            SimpleNamespace(x_min=0, x_max=9, y_min=0, y_max=9),
            SimpleNamespace(x_min=20, x_max=29, y_min=0, y_max=9),
            SimpleNamespace(x_min=0, x_max=9, y_min=50, y_max=59),
        ]
        picked = filter_corridor_rects(
            rects, 5.0, 5.0, heading, depth_m=30.0, half_width_m=10.0,
        )
        self.assertEqual(len(picked), 1)
        self.assertEqual(picked[0].x_min, 20)


if __name__ == "__main__":
    unittest.main()
