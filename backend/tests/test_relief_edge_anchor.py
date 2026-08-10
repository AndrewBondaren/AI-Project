"""Unit: edgeRoadAnchor + obstacle light + seed clearance."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.edgeRoadAnchor import (
    edge_road_abutment,
)
from app.application.worldData.generators.terrain.relief.gradeObstacleLight import (
    is_grade_obstacle_light,
)
from app.application.worldData.generators.terrain.relief.gradePass import (
    grade_from_template,
)
from app.application.worldData.generators.terrain.relief.ribbonSeedResolve import (
    SeedClearance,
    SeedClearanceSkip,
    resolve_seed_clearance,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    WHY_CLEARANCE_L_EFF,
)
from app.dataModel.terrain.relief import ReliefTemplate
from app.dataModel.terrain.relief.enums import ReliefGradeObstaclePolicy
from app.dataModel.terrain.relief.worldReliefGradeObstacle import (
    WorldReliefGradeObstacleScalars,
)


class EdgeRoadAnchorTest(unittest.TestCase):
    def test_abutment_is_seed_minus_outward(self) -> None:
        road = {(0, 0), (0, 1)}
        self.assertEqual(edge_road_abutment((1, 0), (1, 0), road), (0, 0))
        self.assertIsNone(edge_road_abutment((1, 0), (1, 0), {(9, 9)}))

    def test_obstacle_road_and_pin(self) -> None:
        road = {(0, 0)}
        pins = {(2, 0)}

        def blocked(c: tuple[int, int]) -> bool:
            return c in pins

        self.assertTrue(
            is_grade_obstacle_light((0, 0), ref_cells=road, cell_blocked=blocked)
        )
        self.assertTrue(
            is_grade_obstacle_light((2, 0), ref_cells=road, cell_blocked=blocked)
        )
        self.assertFalse(
            is_grade_obstacle_light((1, 0), ref_cells=road, cell_blocked=blocked)
        )

    def test_clearance_truncate_skip(self) -> None:
        from app.db.models.world import World

        road = {(0, 0)}
        # seed at (1,0); free only that cell; pin at (2,0) → gap=1 → L_eff=0
        w = World(
            world_uid="w",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_grade_obstacle_policy=ReliefGradeObstaclePolicy.TRUNCATE_SKIP.value,
        )
        pins = {(2, 0)}
        out = resolve_seed_clearance(
            seed=(1, 0),
            ref_cells=road,
            requested_length=3,
            world=w,
            cell_blocked=lambda c: c in pins,
        )
        self.assertIsInstance(out, SeedClearanceSkip)
        assert isinstance(out, SeedClearanceSkip)
        self.assertEqual(out.why, WHY_CLEARANCE_L_EFF)

        w2 = World(
            world_uid="w",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_grade_obstacle_policy=ReliefGradeObstaclePolicy.ALLOW_FLUSH.value,
        )
        out2 = resolve_seed_clearance(
            seed=(1, 0),
            ref_cells=road,
            requested_length=3,
            world=w2,
            cell_blocked=lambda c: c in pins,
        )
        self.assertIsInstance(out2, SeedClearance)
        assert isinstance(out2, SeedClearance)
        self.assertEqual(out2.L_eff, 1)
        self.assertEqual(out2.outward, (1, 0))

    def test_decision_carries_geom(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "s",
            "display_name": "S",
            "context": "road_shoulder",
            "slope_length_cells": 2,
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {
                        "policy": "slope_down",
                        "delta_z": 1,
                        "slope_weight": 1.0,
                        "sheer_weight": 0.0,
                    },
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        d = grade_from_template(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=2,
            world_seed="s",
            site_id="1",
        )
        self.assertFalse(d.skipped)
        self.assertIsNotNone(d.geom)
        self.assertEqual(d.h, 2)
        self.assertEqual(d.requested_length, d.geom.L)  # type: ignore[union-attr]
        self.assertEqual(
            WorldReliefGradeObstacleScalars.canonical_defaults().relief_grade_obstacle_policy,
            ReliefGradeObstaclePolicy.TRUNCATE_SKIP,
        )


if __name__ == "__main__":
    unittest.main()
