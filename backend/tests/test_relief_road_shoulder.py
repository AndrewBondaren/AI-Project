"""Unit: road_shoulder segmentize + grade."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    grade_road_shoulder_segments,
    segmentize_by_terrain,
)
from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
from app.dataModel.terrain.relief import ReliefTemplate
from app.db.models.world import World


class RoadShoulderGradeTest(unittest.TestCase):
    def test_segmentize_splits_on_terrain(self) -> None:
        cells = [
            ((0, 0), "plains", 2),
            ((1, 0), "plains", 2),
            ((2, 0), "forest", 3),
            ((3, 0), "forest", 3),
        ]
        segs = segmentize_by_terrain(edge_uid="e1", cells=cells)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0].terrain_key, "plains")
        self.assertEqual(len(segs[0].cell_coords), 2)
        self.assertEqual(segs[1].terrain_key, "forest")

    def test_grade_applies_template(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "intercity_shoulder",
            "display_name": "Shoulder",
            "context": "road_shoulder",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 0.0, "sheer_weight": 1.0},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        uid = relief_template_uid("intercity_shoulder")
        world = World(
            world_uid="w1",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": "road_shoulder",
                "display_template_name": "Shoulder",
            }],
            relief_pick_policy={
                "road_shoulder": {"mode": "fixed", "default_template_uid": uid},
            },
        )
        segs = segmentize_by_terrain(
            edge_uid="e1",
            cells=[((0, 0), "plains", 2)],
        )
        results = grade_road_shoulder_segments(
            world=world,
            world_seed="w1",
            segments=segs,
            templates_by_uid={uid: tpl},
        )
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].decision.skipped)
        self.assertEqual(results[0].decision.kind.value, "sheer")
        self.assertIsNone(results[0].decision.earthen_canal)

    def test_earthen_canal_and_structure_refs(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "ditch_shoulder",
            "display_name": "Ditch",
            "context": "road_shoulder",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {
                        "policy": "slope_down",
                        "delta_z": 1,
                        "slope_weight": 1.0,
                        "sheer_weight": 0.0,
                        "earthen_canal": True,
                        "structure_refs": ["fence_wood"],
                    },
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        uid = relief_template_uid("ditch_shoulder")
        world = World(
            world_uid="w1",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": "road_shoulder",
            }],
            relief_pick_policy={
                "road_shoulder": {"mode": "fixed", "default_template_uid": uid},
            },
        )
        segs = segmentize_by_terrain(
            edge_uid="e1",
            cells=[((0, 0), "plains", 2)],
        )
        results = grade_road_shoulder_segments(
            world=world,
            world_seed="w1",
            segments=segs,
            templates_by_uid={uid: tpl},
        )
        self.assertEqual(len(results), 1)
        d = results[0].decision
        self.assertTrue(d.earthen_canal)
        self.assertEqual(list(d.structure_refs), ["fence_wood"])
        # intent only — no barrier materialize in this layer
        self.assertFalse(d.skipped)


if __name__ == "__main__":
    unittest.main()
