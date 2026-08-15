"""Unit: ReliefTemplate / conditions / side_recipe validators (R26/R32/R33)."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.dataModel.terrain.relief import (
    MountainSideRecipe,
    ReliefConditionTerrain,
    ReliefContext,
    ReliefTemplate,
    ReliefTerrainCondition,
)


class ReliefTemplatePojoTest(unittest.TestCase):
    def test_mode_a_plains_ok(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "intercity_shoulder",
            "display_name": "Intercity",
            "context": "road_shoulder",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 0.8, "sheer_weight": 0.2},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        self.assertEqual(tpl.system_name, "intercity_shoulder")
        self.assertTrue(tpl.conditions[0].is_mode_a)

    def test_mode_a_ravine_ok(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "ravine_soft",
            "display_name": "Ravine soft grade",
            "context": ReliefContext.RAVINE,
            "conditions": [{
                "terrain": ReliefConditionTerrain.RAVINE,
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 0.6, "sheer_weight": 0.4},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        self.assertEqual(tpl.context, ReliefContext.RAVINE)
        self.assertEqual(tpl.conditions[0].terrain, ReliefConditionTerrain.RAVINE)
        self.assertTrue(tpl.conditions[0].is_mode_a)

    def test_weights_sum_reject(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefTemplate.model_validate({
                "system_name": "bad",
                "display_name": "Bad",
                "context": "road_shoulder",
                "conditions": [{
                    "terrain": "plains",
                    "cases": [
                        {"policy": "slope_down", "delta_z": 1, "slope_weight": 0.9, "sheer_weight": 0.4},
                        {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                        {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                    ],
                }],
            })

    def test_mix_a_b_reject(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefTerrainCondition.model_validate({
                "terrain": "forest",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {
                        "policy": "slope_up",
                        "bands": [{"delta_z_min": 1, "slope_weight": 1.0, "sheer_weight": 0.0}],
                    },
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            })

    def test_mountain_conditions_reject(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefTemplate.model_validate({
                "system_name": "rocky",
                "display_name": "Rocky",
                "context": "mountain",
                "conditions": [{
                    "terrain": "mountain",
                    "cases": [
                        {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                        {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                        {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                    ],
                }],
            })

    def test_mountain_side_recipe_modes(self) -> None:
        a = MountainSideRecipe.model_validate({"slope_weight": 0.25, "sheer_weight": 0.75})
        self.assertEqual(a.detect_mode().value, "A")
        b = MountainSideRecipe.model_validate({"side_kinds": ["sheer", "slope"]})
        self.assertEqual(b.detect_mode().value, "B")
        c = MountainSideRecipe.model_validate({"default_side_kind": "slope"})
        self.assertEqual(c.detect_mode().value, "C")
        d = MountainSideRecipe.model_validate({})
        self.assertEqual(d.detect_mode().value, "D")

        tpl = ReliefTemplate.model_validate({
            "system_name": "rocky_scarps",
            "display_name": "Scarps",
            "context": "mountain",
            "side_recipe": {"slope_weight": 0.25, "sheer_weight": 0.75},
        })
        self.assertIsNotNone(tpl.side_recipe)

    def test_non_mountain_side_recipe_reject(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefTemplate.model_validate({
                "system_name": "x",
                "display_name": "X",
                "context": "shore",
                "side_recipe": {"default_side_kind": "slope"},
            })

    def test_geom_xor_length_ok(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "len2",
            "display_name": "Len2",
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
                        "slope_length_cells": 3,
                    },
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        self.assertEqual(tpl.outward_length_cells(), 2)
        self.assertEqual(tpl.conditions[0].cases[0].outward_length_cells(), 3)

    def test_geom_xor_both_reject(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefTemplate.model_validate({
                "system_name": "both",
                "display_name": "Both",
                "context": "road_shoulder",
                "slope_length_cells": 2,
                "target_angle_deg": 30.0,
                "conditions": [],
            })

    def test_shoulder_width_removed_reject(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefTemplate.model_validate({
                "system_name": "legacy",
                "display_name": "Legacy",
                "context": "road_shoulder",
                "shoulder_width_cells": 2,
                "conditions": [],
            })


if __name__ == "__main__":
    unittest.main()
