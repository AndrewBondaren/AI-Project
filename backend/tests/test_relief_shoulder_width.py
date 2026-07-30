"""Unit: RELIEF-T-16 shoulder width expand."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.shoulderWidth import (
    expand_shoulder_ring,
    relief_dz,
)


class ShoulderWidthTest(unittest.TestCase):
    def test_width_1_is_seeds(self) -> None:
        seeds = {(1, 0), (2, 0)}
        road = {(0, 0), (0, 1)}
        self.assertEqual(expand_shoulder_ring(seeds, road, 1), seeds)

    def test_width_3_grows_away_from_road(self) -> None:
        # road at x=0; seed at (1,0); width 3 → (1,0),(2,0),(3,0)
        seeds = {(1, 0)}
        road = {(0, 0)}
        out = expand_shoulder_ring(seeds, road, 3)
        self.assertIn((1, 0), out)
        self.assertIn((2, 0), out)
        self.assertIn((3, 0), out)
        self.assertNotIn((0, 0), out)

    def test_does_not_enter_road(self) -> None:
        seeds = {(1, 0)}
        road = {(0, 0), (2, 0)}  # road on both sides
        out = expand_shoulder_ring(seeds, road, 3)
        self.assertEqual(out, {(1, 0)})

    def test_relief_dz_sign(self) -> None:
        self.assertEqual(relief_dz(10, 7), 3)
        self.assertEqual(relief_dz(5, 8), -3)


if __name__ == "__main__":
    unittest.main()
