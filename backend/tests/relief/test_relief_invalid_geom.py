"""E6: invalid geometry rejects; no C31 fallback."""

from __future__ import annotations

import math
import unittest
from pydantic import ValidationError
from app.application.jsonValidation.resolve import resolve_result, ResolveContext, UnresolvedModelError
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

    def test_invalid_knobs_reject_without_fallback(self):
        for knobs in ({"slope_length_cells": -1}, {"slope_length_cells": 0},
                      {"slope_length_cells": 2, "target_angle_deg": 30},
                      {"target_angle_deg": 95}, {"target_angle_deg": float("nan")}):
            with self.subTest(knobs=knobs):
                result = resolve_result(ReliefGradeKnobs, {"slope_weight": 1, "sheer_weight": 0, **knobs},
                                        ctx=ResolveContext(validate_only=True))
                self.assertFalse(result.resolved)


class InvalidGeomGenerateTest(unittest.TestCase):
    def test_invalid_nested_wire_rejects_before_generate(self):
        for knobs in ({"slope_length": 0}, {"slope_length": 2, "target_angle": 30},
                      {"slope_length": 0, "sheer_weight": 1}):
            with self.subTest(knobs=knobs), self.assertRaises(ValidationError):
                _shoulder(**knobs)
        with self.assertRaises(ValidationError):
            _open_land(slope_length=0)

    def test_runtime_copy_cannot_bypass_geometry_rejection(self):
        template = _shoulder().model_copy(update={"slope_length_cells": 0})
        for grade in (grade_from_template, grade_constrained):
            with self.subTest(grade=grade.__name__), self.assertRaises(UnresolvedModelError):
                grade(template=template, template_uid="uid", terrain_key="plains", dz=4,
                      world_seed="s", site_id="site")

    def test_valid_geometry_remains_deterministic(self):
        template = _shoulder()
        kwargs = dict(template=template, template_uid="uid", terrain_key="plains", dz=4,
                      world_seed="s", site_id="site")
        self.assertEqual(grade_from_template(**kwargs), grade_from_template(**kwargs))
        self.assertFalse(grade_constrained(**kwargs).skipped)
