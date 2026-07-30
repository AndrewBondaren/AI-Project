"""Relief profile helpers (tz_terrain_relief)."""

import unittest

from app.application.worldData.generators.terrain.relief.profiles import (
    profile_side_fraction,
    sheer_fraction_radial,
    slope_fraction,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.specs import ReliefSideSpec


class TestReliefProfiles(unittest.TestCase):
    def test_slope_smooth_mid(self) -> None:
        self.assertAlmostEqual(slope_fraction(0.0), 1.0)
        self.assertAlmostEqual(slope_fraction(1.0), 0.0)
        mid = slope_fraction(0.5)
        self.assertGreater(mid, 0.0)
        self.assertLess(mid, 1.0)

    def test_sheer_step(self) -> None:
        self.assertEqual(
            sheer_fraction_radial(dist_origin=90.0, radius_m=100.0, band_m=5.0),
            1.0,
        )
        self.assertEqual(
            sheer_fraction_radial(dist_origin=96.0, radius_m=100.0, band_m=5.0),
            0.0,
        )

    def test_profile_dispatch(self) -> None:
        slope = ReliefSideSpec(kind=ReliefSideKind.SLOPE)
        sheer = ReliefSideSpec(kind=ReliefSideKind.SHEER, sheer_band_light=1)
        self.assertGreater(
            profile_side_fraction(
                slope, t=0.3, dist_for_sheer=30.0, outer_m=100.0, light_m=1.0,
            ),
            0.5,
        )
        self.assertEqual(
            profile_side_fraction(
                sheer, t=0.99, dist_for_sheer=99.5, outer_m=100.0, light_m=1.0,
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
