"""Unit: C31 invalid geom → WARN + θ=20° / L≥1; SHEER still L=1."""

from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from app.application.worldData.generators.terrain.relief.geom.geomResolve import (
    length_from_target_angle,
)
from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_INVALID_GEOM,
)
from app.application.worldData.generators.terrain.relief.pick.gradeConstrained import (
    grade_constrained,
)
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    grade_from_template,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.reliefGradeKnobs import (
    GEOM_INVALID_LENGTH,
    ReliefGradeKnobs,
)
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


def _shoulder(
    *,
    slope_length: int | None = 2,
    target_angle: float | None = None,
    sheer_weight: float = 0.0,
) -> ReliefTemplate:
    case: dict = {
        "policy": "slope_down",
        "delta_z": 1,
        "slope_weight": round(1.0 - sheer_weight, 6),
        "sheer_weight": sheer_weight,
    }
    if slope_length is not None:
        case["slope_length_cells"] = slope_length
    if target_angle is not None:
        case["target_angle_deg"] = target_angle
    return ReliefTemplate.model_validate({
        "system_name": "shoulder_c31",
        "display_name": "Shoulder C31",
        "context": "road_shoulder",
        "conditions": [{
            "terrain": "plains",
            "cases": [
                case,
                {
                    "policy": "slope_up",
                    "delta_z": 1,
                    "slope_weight": 1.0,
                    "sheer_weight": 0.0,
                    "slope_length_cells": 2,
                },
                {
                    "policy": "slope_none",
                    "delta_z": 0,
                    "slope_weight": 1.0,
                    "sheer_weight": 0.0,
                },
            ],
        }],
    })


def _open_land(*, slope_length: int) -> ReliefTemplate:
    return ReliefTemplate.model_validate({
        "system_name": "open_land_c31",
        "display_name": "Open land C31",
        "context": "open_land",
        "slope_length_cells": slope_length,
        "conditions": [{
            "terrain": "plains",
            "cases": [
                {
                    "policy": "slope_down",
                    "delta_z": 1,
                    "slope_weight": 1.0,
                    "sheer_weight": 0.0,
                    "slope_length_cells": slope_length,
                },
                {
                    "policy": "slope_up",
                    "delta_z": 1,
                    "slope_weight": 1.0,
                    "sheer_weight": 0.0,
                    "slope_length_cells": slope_length,
                },
                {
                    "policy": "slope_none",
                    "delta_z": 0,
                    "slope_weight": 1.0,
                    "sheer_weight": 0.0,
                },
            ],
        }],
    })


class InvalidGeomPojoTest(unittest.TestCase):
    def test_omit_both_valid(self) -> None:
        knobs = ReliefGradeKnobs.model_validate({
            "slope_weight": 1.0, "sheer_weight": 0.0,
        })
        self.assertIsNone(knobs.geom_invalid_reason())

    def test_l_negative_invalid(self) -> None:
        knobs = ReliefGradeKnobs.model_validate({
            "slope_weight": 1.0,
            "sheer_weight": 0.0,
            "slope_length_cells": -1,
        })
        self.assertEqual(knobs.geom_invalid_reason(), GEOM_INVALID_LENGTH)


class InvalidGeomGenerateTest(unittest.TestCase):
    def test_l_zero_slope_uses_20deg_length(self) -> None:
        tpl = _shoulder(slope_length=0)
        with patch(
            "app.application.worldData.generators.terrain.relief.pick.gradePass.relief_warning",
        ) as warn:
            d = grade_from_template(
                template=tpl,
                template_uid="uid",
                terrain_key="plains",
                dz=4,
                world_seed="s",
                site_id="site",
            )
        self.assertFalse(d.skipped)
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        want = length_from_target_angle(
            4, ReliefGradeKnobs.INVALID_GEOM_FALLBACK_ANGLE_DEG,
        )
        self.assertEqual(want, 11)
        self.assertEqual(d.requested_length, want)
        assert d.geom is not None
        self.assertEqual(d.geom.L, want)
        self.assertAlmostEqual(
            d.geom.angle_deg or 0.0,
            math.degrees(math.atan(4 / want)),
            places=5,
        )
        warn.assert_called()
        self.assertEqual(warn.call_args.args[0], EVENT_INVALID_GEOM)
        self.assertEqual(warn.call_args.kwargs["why"], GEOM_INVALID_LENGTH)

    def test_facade_pass_through_l_zero_same_as_inner(self) -> None:
        tpl = _shoulder(slope_length=0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        want = length_from_target_angle(
            4, ReliefGradeKnobs.INVALID_GEOM_FALLBACK_ANGLE_DEG,
        )
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, want)

    def test_both_keys_same_fallback(self) -> None:
        tpl = _shoulder(slope_length=2, target_angle=30.0)
        d = grade_from_template(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        want = length_from_target_angle(
            4, ReliefGradeKnobs.INVALID_GEOM_FALLBACK_ANGLE_DEG,
        )
        self.assertEqual(d.requested_length, want)

    def test_sheer_ignores_invalid_l(self) -> None:
        tpl = _shoulder(slope_length=0, sheer_weight=1.0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertEqual(d.kind, ReliefSideKind.SHEER)
        self.assertEqual(d.requested_length, 1)
        assert d.geom is not None
        self.assertEqual(d.geom.L, 1)

    def test_plains_envelope_still_clamps_after_fallback(self) -> None:
        tpl = _open_land(slope_length=0)
        d = grade_constrained(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=4,
            world_seed="s",
            site_id="site",
        )
        self.assertEqual(d.kind, ReliefSideKind.SLOPE)
        self.assertEqual(d.requested_length, 20)


if __name__ == "__main__":
    unittest.main()
