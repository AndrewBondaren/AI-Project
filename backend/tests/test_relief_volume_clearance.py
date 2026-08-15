"""Unit: §8b volume plan + §9 free_gap / clearance."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.geom.freeGap import measure_free_gap
from app.application.worldData.generators.terrain.relief.volume.obstacleClearance import (
    outward_length_for_policy,
)
from app.application.worldData.generators.terrain.relief.volume.volumeMaterialize import (
    geom_for_cleared_length,
    plan_ribbon_volume,
    ribbon_sign_from_dz,
)
from app.dataModel.terrain.relief.enums import (
    ReliefGradeObstaclePolicy,
    ReliefSideKind,
)


class FreeGapTest(unittest.TestCase):
    def test_gap_until_obstacle(self) -> None:
        blocked = {(3, 0)}

        def is_blocked(c: tuple[int, int]) -> bool:
            return c in blocked

        self.assertEqual(
            measure_free_gap(start=(1, 0), outward=(1, 0), is_blocked=is_blocked),
            2,
        )
        self.assertEqual(
            measure_free_gap(start=(3, 0), outward=(1, 0), is_blocked=is_blocked),
            0,
        )

    def test_truncate_skip_gap1(self) -> None:
        # TZ example: gap=1 → truncate_skip L_eff=0; allow_flush L_eff=1
        self.assertEqual(
            outward_length_for_policy(
                ReliefGradeObstaclePolicy.TRUNCATE_SKIP,
                requested_length=3,
                free_gap=1,
            ),
            0,
        )
        self.assertEqual(
            outward_length_for_policy(
                ReliefGradeObstaclePolicy.ALLOW_FLUSH,
                requested_length=3,
                free_gap=1,
            ),
            1,
        )


class VolumeMaterializeTest(unittest.TestCase):
    def test_slope_down_closes_delta(self) -> None:
        geom = geom_for_cleared_length(h=4, kind=ReliefSideKind.SLOPE, length=2)
        self.assertEqual(geom.L, 2)
        self.assertEqual(geom.steps, (2, 2))
        plan = plan_ribbon_volume(z_road=10, h=4, sign=-1, geom=geom)
        self.assertEqual([c.surface_z for c in plan.columns], [8, 6])
        self.assertEqual(plan.columns[-1].surface_z, 10 - 4)

    def test_slope_up_closes_delta(self) -> None:
        geom = geom_for_cleared_length(h=3, kind=ReliefSideKind.SLOPE, length=3)
        plan = plan_ribbon_volume(z_road=5, h=3, sign=1, geom=geom)
        self.assertEqual([c.surface_z for c in plan.columns], [6, 7, 8])

    def test_sheer_face_top(self) -> None:
        geom = geom_for_cleared_length(h=6, kind=ReliefSideKind.SHEER, length=2)
        plan = plan_ribbon_volume(z_road=12, h=6, sign=-1, geom=geom)
        self.assertEqual(len(plan.columns), 2)
        self.assertEqual(plan.columns[0].surface_z, 12)
        self.assertIsNone(plan.angle_deg)

    def test_sign_from_dz(self) -> None:
        self.assertEqual(ribbon_sign_from_dz(2), -1)
        self.assertEqual(ribbon_sign_from_dz(-3), 1)

    def test_clearance_shortens_then_volume(self) -> None:
        requested = 4
        gap = 2
        L_eff = outward_length_for_policy(
            ReliefGradeObstaclePolicy.TRUNCATE_SKIP,
            requested_length=requested,
            free_gap=gap,
        )
        self.assertEqual(L_eff, 1)
        geom = geom_for_cleared_length(h=4, kind=ReliefSideKind.SLOPE, length=L_eff)
        plan = plan_ribbon_volume(z_road=10, h=4, sign=-1, geom=geom)
        self.assertEqual(plan.L, 1)
        self.assertEqual(plan.columns[0].surface_z, 6)  # all h in one step


if __name__ == "__main__":
    unittest.main()
