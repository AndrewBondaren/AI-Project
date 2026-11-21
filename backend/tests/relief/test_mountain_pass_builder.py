"""MountainPassBuilder topology unit tests — tz_mountain_architecture."""

import unittest

from app.application.worldData.generators.terrain.mountains.passBuilder import (
    MountainPassBuilder,
)
from app.application.worldData.generators.terrain.mountains.ridgeGraphBuilder import (
    build_mst_graph,
)
from app.application.worldData.generators.terrain.mountains.ridgePlacement import RidgeCandidate
from app.application.worldData.generators.terrain.mountains.systemCluster import (
    cluster_systems,
    vertices_from_peaks,
)
from app.dataModel.terrainMasks.mountain.enums import MountainRangeStyle, mountain_kind_profile
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSpec,
    MountainSaddleSpec,
    MountainSpec,
)
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy


class TestPassBuilderTopology(unittest.TestCase):
    def test_kind_profile_topology_defaults(self) -> None:
        from app.dataModel.terrainMasks.mountain.enums import MountainKind

        profile = mountain_kind_profile(MountainKind.ROCKY)
        self.assertAlmostEqual(profile.peak_gap_inset_fraction, 0.30)
        self.assertAlmostEqual(profile.saddle_rise_fraction, 0.65)

    def test_two_close_peaks_become_range(self) -> None:
        policy = MountainsCategoryPolicy(
            autoresolve=True,
            default_radius_m=200,
            threshold=0.0,
        )
        # Within peak_gap: R*(1-0.3)=140 — place 100m apart
        candidates = [
            RidgeCandidate(0, 0, 10),
            RidgeCandidate(100, 0, 10),
        ]
        out = MountainPassBuilder().build(candidates, policy, seed=1, reserved=[])
        ranges = [e for e in out if isinstance(e, MountainRangeSpec)]
        self.assertGreaterEqual(len(ranges), 1)
        primary = ranges[0]
        self.assertEqual(len(primary.peaks), 2)
        self.assertGreaterEqual(len(primary.saddles), 1)
        self.assertEqual(primary.style, MountainRangeStyle.BROKEN)

    def test_far_peaks_remain_separate(self) -> None:
        policy = MountainsCategoryPolicy(autoresolve=True, default_radius_m=100)
        # peak_gap = 70; place 500m apart
        candidates = [
            RidgeCandidate(0, 0, 10),
            RidgeCandidate(500, 0, 10),
        ]
        out = MountainPassBuilder().build(candidates, policy, seed=1, reserved=[])
        specs = [e for e in out if isinstance(e, MountainSpec)]
        ranges = [e for e in out if isinstance(e, MountainRangeSpec)]
        self.assertEqual(len(specs), 2)
        # Secondary may still create ranges from singles? No — singles stay MountainSpec.
        # Secondary only from primary ranges.
        self.assertEqual(len(ranges), 0)

    def test_mst_two_vertices(self) -> None:
        peaks = [
            MountainSpec(origin_x_m=0, origin_y_m=0, radius_m=200),
            MountainSpec(origin_x_m=80, origin_y_m=0, radius_m=200),
        ]
        verts = vertices_from_peaks(peaks)
        # peak_gap = 200*0.7 = 140 > 80 → one system
        systems = cluster_systems(verts)
        self.assertEqual(len(systems), 1)
        g = build_mst_graph(list(systems[0].vertices))
        self.assertEqual(len(g.edges), 1)

    def test_saddle_spec_wire(self) -> None:
        s = MountainSaddleSpec(peak_a_index=0, peak_b_index=1, t=0.4, rise_fraction=0.5)
        r = MountainRangeSpec(
            spine=[(0, 0), (100, 0)],
            peaks=[
                MountainSpec(origin_x_m=0, origin_y_m=0),
                MountainSpec(origin_x_m=100, origin_y_m=0),
            ],
            saddles=[s],
            saddle_rise_fraction=0.7,
        )
        self.assertEqual(r.saddles[0].t, 0.4)
        self.assertEqual(r.saddle_rise_fraction, 0.7)


if __name__ == "__main__":
    unittest.main()
