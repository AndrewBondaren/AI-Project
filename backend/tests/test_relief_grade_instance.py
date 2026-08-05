"""Unit: ReliefGradeInstance POJO + factory (§8c)."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.gradeInstanceFactory import (
    build_ribbon_grade_instance,
    make_grade_uid,
)
from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    RibbonColumnPlan,
    RibbonVolumePlan,
)
from app.application.worldData.persistReliefGrades import instance_to_row
from app.dataModel.terrain.relief import ReliefGradeInstance, ReliefGradeSystem
from app.dataModel.terrain.relief.enums import ReliefSideKind
from pydantic import ValidationError


class ReliefGradeInstanceTest(unittest.TestCase):
    def test_uid_deterministic(self) -> None:
        a = make_grade_uid(world_uid="w", site_id="s", seed=(1, 2))
        b = make_grade_uid(world_uid="w", site_id="s", seed=(1, 2))
        self.assertEqual(a, b)
        self.assertNotEqual(
            a, make_grade_uid(world_uid="w", site_id="s", seed=(1, 3)),
        )

    def test_slope_instance(self) -> None:
        plan = RibbonVolumePlan(
            kind=ReliefSideKind.SLOPE,
            h=2,
            L=2,
            angle_deg=45.0,
            sign=-1,
            columns=(
                RibbonColumnPlan(k=1, surface_z=9),
                RibbonColumnPlan(k=2, surface_z=8),
            ),
        )
        inst = build_ribbon_grade_instance(
            world_uid="w1",
            site_id="e|plains|1,0",
            seed=(1, 0),
            plan=plan,
            cell_refs=((1, 0), (2, 0)),
            facing="west",
            earthen_canal=False,
            template_uid="tpl",
            edge_uid="edge1",
        )
        self.assertEqual(inst.kind, ReliefSideKind.SLOPE)
        self.assertEqual(inst.height_cells, 2)
        self.assertEqual(inst.length_cells, 2)
        self.assertAlmostEqual(inst.angle_deg or 0.0, 45.0)
        self.assertEqual(inst.facing, "west")
        self.assertEqual(len(inst.cell_refs), 2)
        row = instance_to_row(inst, created_at="2026-01-01T00:00:00Z")
        self.assertEqual(row.kind, "slope")
        self.assertEqual(row.cell_refs, [[1, 0], [2, 0]])

    def test_sheer_rejects_angle(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefGradeInstance(
                grade_uid="g",
                world_uid="w",
                kind=ReliefSideKind.SHEER,
                height_cells=3,
                length_cells=1,
                cell_refs=[(0, 0)],
                angle_deg=45.0,
            )

    def test_system_requires_two(self) -> None:
        with self.assertRaises(ValidationError):
            ReliefGradeSystem(
                grade_system_uid="sys",
                world_uid="w",
                grade_uids=["only-one"],
            )
        ok = ReliefGradeSystem(
            grade_system_uid="sys",
            world_uid="w",
            grade_uids=["a", "b"],
        )
        self.assertEqual(len(ok.grade_uids), 2)


if __name__ == "__main__":
    unittest.main()
