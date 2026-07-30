"""PassBuilder review-fix units — spacing, saddles, secondary, facing corridor."""

import unittest

from app.application.worldData.generators.terrain.mountains.passBuilder import (
    MountainPassBuilder,
)
from app.application.worldData.generators.terrain.mountains.peakGap import resolve_peak_gap_m
from app.application.worldData.generators.terrain.mountains.rangeCompose import (
    compose_range_corridor,
)
from app.application.worldData.generators.terrain.mountains.ridgePlacement import RidgeCandidate
from app.application.worldData.generators.terrain.mountains.saddlePlacer import (
    validate_saddle_peak_indices,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrainMasks.mountain.enums import MountainKind
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSpec,
    MountainSaddleSpec,
    MountainSideSpec,
    MountainSpec,
    MountainRangeSides,
)
from app.dataModel.terrainMasks.mountain.enums import MountainSideKind
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy


class TestPeakGapResolve(unittest.TestCase):
    def test_declared_peak_spacing_wins(self) -> None:
        spec = MountainRangeSpec(
            spine=[(0, 0), (100, 0)],
            peak_spacing_m=77,
            kind=MountainKind.ROCKY,
        )
        self.assertEqual(
            resolve_peak_gap_m(kind=MountainKind.ROCKY, radius_m=500, range_spec=spec),
            77.0,
        )

    def test_peak_spacings_min_wins(self) -> None:
        spec = MountainRangeSpec(
            spine=[(0, 0), (100, 0), (200, 0)],
            peak_spacings_m=[90, 40],
            kind=MountainKind.ROCKY,
        )
        self.assertEqual(
            resolve_peak_gap_m(kind=MountainKind.ROCKY, radius_m=500, range_spec=spec),
            40.0,
        )

    def test_auto_inset(self) -> None:
        gap = resolve_peak_gap_m(kind=MountainKind.ROCKY, radius_m=200)
        self.assertAlmostEqual(gap, 200 * 0.7)


class TestSaddleContract(unittest.TestCase):
    def test_invalid_index_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_saddle_peak_indices(
                MountainSaddleSpec(peak_a_index=0, peak_b_index=5),
                n_peaks=2,
            )

    def test_same_index_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_saddle_peak_indices(
                MountainSaddleSpec(peak_a_index=1, peak_b_index=1),
                n_peaks=3,
            )

    def test_auto_range_stamps_spacing_and_contiguous_saddles(self) -> None:
        policy = MountainsCategoryPolicy(
            autoresolve=True,
            default_radius_m=200,
            enable_secondary_ridges=False,
        )
        out = MountainPassBuilder().build(
            [RidgeCandidate(0, 0, 10), RidgeCandidate(100, 0, 10)],
            policy,
            seed=1,
            reserved=[],
        )
        ranges = [e for e in out if isinstance(e, MountainRangeSpec)]
        self.assertEqual(len(ranges), 1)
        primary = ranges[0]
        self.assertIsNotNone(primary.peak_spacing_m)
        self.assertGreaterEqual(primary.peak_spacing_m, 1)
        self.assertEqual(len(primary.saddles), 1)
        s = primary.saddles[0]
        self.assertEqual({s.peak_a_index, s.peak_b_index}, {0, 1})


class TestSecondaryGate(unittest.TestCase):
    def test_secondary_off(self) -> None:
        policy = MountainsCategoryPolicy(
            autoresolve=True,
            default_radius_m=200,
            enable_secondary_ridges=False,
        )
        out = MountainPassBuilder().build(
            [RidgeCandidate(0, 0, 10), RidgeCandidate(100, 0, 10)],
            policy,
            seed=1,
            reserved=[],
        )
        ranges = [e for e in out if isinstance(e, MountainRangeSpec)]
        self.assertEqual(len(ranges), 1)


class TestCorridorFacing(unittest.TestCase):
    def test_slope_corridor_has_facing_toward_spine(self) -> None:
        spec = MountainRangeSpec(
            spine=[(0, 0), (100, 0)],
            width_m=40,
            sides=MountainRangeSides(
                left=MountainSideSpec(kind=MountainSideKind.SLOPE),
                right=MountainSideSpec(kind=MountainSideKind.SLOPE),
            ),
        )
        # Point north of spine → uphill south toward spine
        points = [(0, 50.0, 15.0)]
        fractions, facing = compose_range_corridor(spec, points, light_m=1.0)
        self.assertIn(0, fractions)
        self.assertEqual(facing[0], Facing.SOUTH.value)

    def test_sheer_corridor_facing_none(self) -> None:
        spec = MountainRangeSpec(
            spine=[(0, 0), (100, 0)],
            width_m=40,
            sides=MountainRangeSides(
                left=MountainSideSpec(kind=MountainSideKind.SHEER, sheer_band_light=1),
                right=MountainSideSpec(kind=MountainSideKind.SHEER, sheer_band_light=1),
            ),
        )
        points = [(0, 50.0, 5.0)]
        _frac, facing = compose_range_corridor(spec, points, light_m=1.0)
        self.assertIn(0, facing)
        self.assertIsNone(facing[0])


if __name__ == "__main__":
    unittest.main()
