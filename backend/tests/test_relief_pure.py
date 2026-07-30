"""Unit tests for relief pure modules (classify / pick / mountain sides)."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.conditionNormalize import (
    normalize_condition,
)
from app.application.worldData.generators.terrain.relief.kindRoll import kind_roll
from app.application.worldData.generators.terrain.relief.mountainSideMaterialize import (
    resolve_sides_with_declare,
)
from app.application.worldData.generators.terrain.relief.slopeClassify import classify
from app.application.worldData.generators.terrain.relief.templatePick import pick_template
from app.dataModel.terrain.relief import (
    ReliefSideKind,
    ReliefSideSpec,
    ReliefTemplate,
    ReliefTerrainCondition,
    WorldReliefPickPolicy,
    WorldReliefTemplateRegistry,
)
from app.dataModel.terrain.relief.enums import ReliefPickMode, ReliefSlopePolicy
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


if __name__ == "__main__":
    unittest.main()
