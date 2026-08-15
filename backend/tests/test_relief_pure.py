"""Unit tests for relief pure modules (classify / pick / mountain sides)."""

from __future__ import annotations

import math
import unittest

from app.application.worldData.generators.terrain.relief.pick.conditionNormalize import (
    normalize_condition,
)
from app.application.worldData.generators.terrain.relief.pick.kindRoll import kind_roll
from app.application.worldData.generators.terrain.relief.mountain.mountainSideMaterialize import (
    resolve_sides_with_declare,
)
from app.application.worldData.generators.terrain.relief.pick.slopeClassify import classify
from app.application.worldData.generators.terrain.relief.pick.templatePick import pick_template
from app.application.worldData.generators.terrain.relief.geom.geomResolve import (
    angle_from_height_length,
    geom_resolve,
    length_from_target_angle,
    partition_height,
)
from app.application.worldData.generators.terrain.relief.volume.obstacleClearance import (
    outward_length_for_policy,
)
from app.dataModel.terrain.relief import (
    ReliefGradeObstaclePolicy,
    ReliefSideKind,
    ReliefSideSpec,
    ReliefTemplate,
    ReliefTerrainCondition,
    WorldReliefPickPolicy,
    WorldReliefTemplateRegistry,
)
from app.dataModel.terrain.relief.enums import (
    ReliefContext,
    ReliefPickMode,
    ReliefSlopePolicy,
)
from app.dataModel.terrain.relief.worldReliefGradeObstacle import (
    WorldReliefGradeObstacleScalars,
)
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy


class ReliefPureTest(unittest.TestCase):
    def test_classify_mode_a_order(self) -> None:
        cond = ReliefTerrainCondition.model_validate({
            "terrain": "plains",
            "cases": [
                {"policy": "slope_down", "delta_z": 1, "slope_weight": 0.8, "sheer_weight": 0.2},
                {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
            ],
        })
        schedule = normalize_condition(cond)
        none = classify(0, schedule)
        assert none is not None
        self.assertEqual(none.policy, ReliefSlopePolicy.SLOPE_NONE)
        down = classify(2, schedule)
        assert down is not None
        self.assertEqual(down.policy, ReliefSlopePolicy.SLOPE_DOWN)
        up = classify(-3, schedule)
        assert up is not None
        self.assertEqual(up.policy, ReliefSlopePolicy.SLOPE_UP)

    def test_kind_roll_deterministic(self) -> None:
        a = kind_roll(
            world_seed="s", context="road_shoulder", template_uid="t",
            site_id="1", slope_weight=0.5, sheer_weight=0.5,
        )
        b = kind_roll(
            world_seed="s", context="road_shoulder", template_uid="t",
            site_id="1", slope_weight=0.5, sheer_weight=0.5,
        )
        self.assertEqual(a, b)

    def test_pick_fixed(self) -> None:
        reg = WorldReliefTemplateRegistry.model_validate([
            {
                "system_template_uid": "uid-a",
                "context": "mountain",
                "display_template_name": "A",
            },
            {
                "system_template_uid": "uid-b",
                "context": "mountain",
            },
        ])
        policy = WorldReliefPickPolicy(
            mountain=ReliefContextPickPolicy(
                mode=ReliefPickMode.FIXED,
                default_template_uid="uid-b",
            ),
        )
        result = pick_template(
            context="mountain",
            registry=reg,
            world_policy=policy,
            world_seed="seed",
            site_id="m1",
        )
        self.assertEqual(result.template_uid, "uid-b")
        self.assertEqual(result.policy_level, "world")

    def test_ravine_world_pick_fixed(self) -> None:
        reg = WorldReliefTemplateRegistry.model_validate([
            {
                "system_template_uid": "uid-ravine",
                "context": ReliefContext.RAVINE,
            },
        ])
        policy = WorldReliefPickPolicy(
            ravine=ReliefContextPickPolicy(
                mode=ReliefPickMode.FIXED,
                default_template_uid="uid-ravine",
            ),
        )
        result = pick_template(
            context=ReliefContext.RAVINE,
            registry=reg,
            world_policy=policy,
            world_seed="seed",
            site_id="rv1",
        )
        self.assertEqual(result.template_uid, "uid-ravine")
        self.assertEqual(result.policy_level, "world")

    def test_mountain_recipe_d_reproducible(self) -> None:
        sides1 = resolve_sides_with_declare(
            n=4,
            recipe=None,
            world_seed="world",
            template_uid="wild",
            mountain_id="peak1",
            declare_sides=[],
        )
        sides2 = resolve_sides_with_declare(
            n=4,
            recipe=None,
            world_seed="world",
            template_uid="wild",
            mountain_id="peak1",
            declare_sides=[],
        )
        self.assertEqual([s.kind for s in sides1], [s.kind for s in sides2])

    def test_declare_wins(self) -> None:
        declare = [
            ReliefSideSpec(kind=ReliefSideKind.SLOPE),
            ReliefSideSpec(kind=ReliefSideKind.SHEER),
        ]
        out = resolve_sides_with_declare(
            n=2,
            recipe=None,
            world_seed="w",
            template_uid="t",
            mountain_id="m",
            declare_sides=declare,
        )
        self.assertEqual([s.kind for s in out], [ReliefSideKind.SLOPE, ReliefSideKind.SHEER])

    def test_obstacle_policy_leff(self) -> None:
        skip = ReliefGradeObstaclePolicy.TRUNCATE_SKIP
        flush = ReliefGradeObstaclePolicy.ALLOW_FLUSH
        self.assertEqual(outward_length_for_policy(skip, requested_length=3, free_gap=1), 0)
        self.assertEqual(outward_length_for_policy(flush, requested_length=3, free_gap=1), 1)
        self.assertEqual(outward_length_for_policy(skip, requested_length=3, free_gap=2), 1)
        self.assertEqual(outward_length_for_policy(flush, requested_length=3, free_gap=2), 2)
        self.assertEqual(
            WorldReliefGradeObstacleScalars.canonical_defaults().relief_grade_obstacle_policy,
            ReliefGradeObstaclePolicy.TRUNCATE_SKIP,
        )

    def test_partition_height_canon(self) -> None:
        self.assertEqual(partition_height(1, 1), (1,))
        self.assertEqual(partition_height(4, 2), (2, 2))
        self.assertEqual(partition_height(5, 2), (3, 2))
        self.assertEqual(partition_height(3, 5), (1, 1, 1, 0, 0))
        self.assertEqual(sum(partition_height(5, 2)), 5)

    def test_partition_height_matrix_h_l_1_to_4(self) -> None:
        """Raw partition for every (h,L) in 1..4 — includes flat tails when h < L."""
        expected = {
            (1, 1): (1,),
            (1, 2): (1, 0),
            (1, 3): (1, 0, 0),
            (1, 4): (1, 0, 0, 0),
            (2, 1): (2,),
            (2, 2): (1, 1),
            (2, 3): (1, 1, 0),
            (2, 4): (1, 1, 0, 0),
            (3, 1): (3,),
            (3, 2): (2, 1),
            (3, 3): (1, 1, 1),
            (3, 4): (1, 1, 1, 0),
            (4, 1): (4,),
            (4, 2): (2, 2),
            (4, 3): (2, 1, 1),
            (4, 4): (1, 1, 1, 1),
        }
        for h in range(1, 5):
            for L in range(1, 5):
                steps = partition_height(h, L)
                self.assertEqual(steps, expected[(h, L)], msg=f"h={h} L={L}")
                self.assertEqual(sum(steps), h)
                self.assertEqual(len(steps), L)

    def test_geom_a_matrix_h_l_1_to_4(self) -> None:
        """Geom-A resolve: L_eff=min(L,h); steps all ≥1; θ=atan(h/L_eff)."""
        # Realized angle (deg) after clamp — cubic cell.
        # Diagonal h==L → 45°; L>h clamps to L_eff=h → also 45°;
        # L<h → steeper than 45°.
        expected_angle = {
            (1, 1): 45.0,
            (1, 2): 45.0,   # clamp L→1
            (1, 3): 45.0,
            (1, 4): 45.0,
            (2, 1): math.degrees(math.atan(2 / 1)),  # ~63.43
            (2, 2): 45.0,
            (2, 3): 45.0,   # clamp L→2
            (2, 4): 45.0,
            (3, 1): math.degrees(math.atan(3 / 1)),  # ~71.57
            (3, 2): math.degrees(math.atan(3 / 2)),  # ~56.31
            (3, 3): 45.0,
            (3, 4): 45.0,   # clamp L→3
            (4, 1): math.degrees(math.atan(4 / 1)),  # ~75.96
            (4, 2): math.degrees(math.atan(4 / 2)),  # ~63.43
            (4, 3): math.degrees(math.atan(4 / 3)),  # ~53.13
            (4, 4): 45.0,
        }
        expected_steps = {
            (1, 1): (1,),
            (1, 2): (1,),
            (1, 3): (1,),
            (1, 4): (1,),
            (2, 1): (2,),
            (2, 2): (1, 1),
            (2, 3): (1, 1),
            (2, 4): (1, 1),
            (3, 1): (3,),
            (3, 2): (2, 1),
            (3, 3): (1, 1, 1),
            (3, 4): (1, 1, 1),
            (4, 1): (4,),
            (4, 2): (2, 2),
            (4, 3): (2, 1, 1),
            (4, 4): (1, 1, 1, 1),
        }
        for h in range(1, 5):
            for L in range(1, 5):
                g = geom_resolve(
                    h=h,
                    kind=ReliefSideKind.SLOPE,
                    slope_length_cells=L,
                )
                L_eff = min(L, h)
                self.assertEqual(g.h, h, msg=f"h={h} L={L}")
                self.assertEqual(g.L, L_eff, msg=f"h={h} L={L}")
                self.assertEqual(g.steps, expected_steps[(h, L)], msg=f"h={h} L={L}")
                self.assertEqual(sum(g.steps), h, msg=f"h={h} L={L}")
                self.assertTrue(all(s >= 1 for s in g.steps), msg=f"h={h} L={L}")
                self.assertAlmostEqual(
                    g.angle_deg or 0.0,
                    expected_angle[(h, L)],
                    places=5,
                    msg=f"h={h} L={L}",
                )
                self.assertAlmostEqual(
                    angle_from_height_length(h, L_eff),
                    expected_angle[(h, L)],
                    places=5,
                    msg=f"h={h} L={L}",
                )

    def test_geom_b_length_then_clamp(self) -> None:
        # Formula: h=2, θ=30 → L≈4; resolve clamps L_eff=min(L,h)=2 → realized 45°
        self.assertEqual(length_from_target_angle(2, 30.0), 4)
        g = geom_resolve(
            h=2,
            kind=ReliefSideKind.SLOPE,
            target_angle_deg=30.0,
        )
        self.assertEqual(g.L, 2)
        self.assertEqual(sum(g.steps), 2)
        self.assertTrue(all(s >= 1 for s in g.steps))
        self.assertAlmostEqual(g.angle_deg or 0.0, 45.0, places=5)

    def test_geom_b_matrix_angles_for_h_1_to_4(self) -> None:
        """Geom-B: L_raw=ceil(h/tanθ); after clamp θ_realized ≥ 45° when cubic + steps≥1."""
        # Gentle targets (<45°) always clamp to L_eff=h → realized 45°.
        for h in range(1, 5):
            for target in (20.0, 30.0, 40.0):
                L_raw = length_from_target_angle(h, target)
                self.assertGreaterEqual(L_raw, h, msg=f"h={h} θ={target}")
                g = geom_resolve(
                    h=h,
                    kind=ReliefSideKind.SLOPE,
                    target_angle_deg=target,
                )
                self.assertEqual(g.L, h)
                self.assertAlmostEqual(g.angle_deg or 0.0, 45.0, places=5)

        # Steeper than 45°: L_raw < h possible → keep steep realized angle.
        # h=4, θ=60 → L=ceil(4/tan60)=ceil(2.309)=3 → L_eff=3 → atan(4/3)≈53.13
        self.assertEqual(length_from_target_angle(4, 60.0), 3)
        g60 = geom_resolve(h=4, kind=ReliefSideKind.SLOPE, target_angle_deg=60.0)
        self.assertEqual(g60.L, 3)
        self.assertAlmostEqual(g60.angle_deg or 0.0, math.degrees(math.atan(4 / 3)), places=5)
        self.assertEqual(sum(g60.steps), 4)

        # h=4, θ=75 → L=ceil(4/tan75)=ceil(1.072)=2 → atan(4/2)=63.43
        self.assertEqual(length_from_target_angle(4, 75.0), 2)
        g75 = geom_resolve(h=4, kind=ReliefSideKind.SLOPE, target_angle_deg=75.0)
        self.assertEqual(g75.L, 2)
        self.assertAlmostEqual(g75.angle_deg or 0.0, math.degrees(math.atan(4 / 2)), places=5)

    def test_geom_explicit_zero_no_bump(self) -> None:
        """Wire L=0 → ResolvedGeom.L=0; no silent max(1,L) / no partition."""
        for kind in (ReliefSideKind.SLOPE, ReliefSideKind.SHEER):
            g = geom_resolve(h=4, kind=kind, slope_length_cells=0)
            self.assertEqual(g.L, 0, msg=kind.value)
            self.assertEqual(g.steps, ())
            self.assertEqual(g.h, 4)
        # omit L → default 1
        g_def = geom_resolve(h=4, kind=ReliefSideKind.SLOPE)
        self.assertEqual(g_def.L, 1)
        self.assertEqual(sum(g_def.steps), 4)

    def test_sheer_l_times_h(self) -> None:
        g = geom_resolve(
            h=6,
            kind=ReliefSideKind.SHEER,
            slope_length_cells=2,
        )
        self.assertEqual(g.h, 6)
        self.assertEqual(g.L, 2)
        self.assertIsNone(g.angle_deg)
        self.assertEqual(g.steps, ())
        # Geom-B ignored for SHEER
        g2 = geom_resolve(
            h=6,
            kind=ReliefSideKind.SHEER,
            target_angle_deg=30.0,
        )
        self.assertEqual(g2.L, 1)

        # SHEER L matrix: no clamp to h (XY columns independent of vertical h)
        for h in range(1, 5):
            for L in range(1, 5):
                gs = geom_resolve(
                    h=h,
                    kind=ReliefSideKind.SHEER,
                    slope_length_cells=L,
                )
                self.assertEqual(gs.L, L, msg=f"SHEER h={h} L={L}")
                self.assertEqual(gs.h, h)
                self.assertIsNone(gs.angle_deg)
                self.assertEqual(gs.steps, ())


if __name__ == "__main__":
    unittest.main()
