"""Unit: Wave B4 — RELIEF-T-54 Intent omit + RELIEF-T-64 honest skip reason."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.gradePass import (
    RibbonGradeDecision,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    WHY_EMPTY_PLAN,
    WHY_H_LT_1,
    WHY_NO_EDGE_ROAD_ANCHOR,
    WHY_NOT_STAMPED,
)
from app.application.worldData.generators.terrain.relief.ribbonSegmentize import (
    RibbonSegment,
)
from app.application.worldData.generators.terrain.relief.ribbonGrade import (
    RibbonGradeResult,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderMaterialize import (
    SegmentMaterializeResult,
    _aggregate_skip_why,
)
from app.application.worldData.pack.bake.lightGrid.ribbonIntent import (
    RibbonIntent,
    to_intent,
)
from app.dataModel.terrain.relief.canal import EarthenCanal
from app.dataModel.terrain.relief.enums import ReliefSideKind


def _result(
    *,
    skipped: bool = False,
    earthen: bool | None = None,
    reason: str = "",
    kind: ReliefSideKind | None = ReliefSideKind.SHEER,
) -> RibbonGradeResult:
    seg = RibbonSegment(
        owner_uid="e1",
        terrain_key="plains",
        system_terrain="plains",
        dz=1,
        site_id="e1|plains|0,0",
        cell_coords=((0, 0),),
    )
    decision = RibbonGradeDecision(
        template_uid="t1",
        policy=None,
        kind=kind,
        requested_length=1,
        h=1,
        geom=None,
        earthen_canal=earthen,
        structure_refs=(),
        reason=reason,
        skipped=skipped,
        structure_canal=None,
    )
    return RibbonGradeResult(
        segment=seg, decision=decision, template_uid="t1",
    )


class IntentOmitT54Test(unittest.TestCase):
    def test_skipped_omit_earthen_is_none_not_false(self) -> None:
        intent = to_intent(_result(skipped=True, earthen=None), ())
        self.assertTrue(intent.skipped)
        self.assertIsNone(intent.canal)
        self.assertIsNone(intent.earthen_canal)

    def test_skipped_does_not_synthesize_earthen_from_knobs(self) -> None:
        intent = to_intent(_result(skipped=True, earthen=True), ())
        self.assertTrue(intent.skipped)
        self.assertIsNone(intent.canal)
        self.assertIsNone(intent.earthen_canal)

    def test_drawn_earthen_still_true(self) -> None:
        intent = RibbonIntent(
            owner_uid="e1",
            site_id="s",
            template_uid="t",
            kind="sheer",
            width=1,
            cell_coords=(),
            skipped=False,
            canal=EarthenCanal(),
        )
        self.assertTrue(intent.earthen_canal)

    def test_fence_only_extras_earthen_false(self) -> None:
        intent = RibbonIntent(
            owner_uid="e1",
            site_id="s",
            template_uid="t",
            kind="sheer",
            width=1,
            cell_coords=(),
            skipped=False,
            canal=None,
            extra_structure_refs=("fence_wood",),
        )
        self.assertIs(intent.earthen_canal, False)


class SkipReasonT64Test(unittest.TestCase):
    def test_aggregate_single_why(self) -> None:
        self.assertEqual(
            _aggregate_skip_why([WHY_NO_EDGE_ROAD_ANCHOR, WHY_NO_EDGE_ROAD_ANCHOR]),
            WHY_NO_EDGE_ROAD_ANCHOR,
        )

    def test_aggregate_mixed_is_not_stamped(self) -> None:
        self.assertEqual(
            _aggregate_skip_why([WHY_NO_EDGE_ROAD_ANCHOR, WHY_EMPTY_PLAN]),
            WHY_NOT_STAMPED,
        )

    def test_aggregate_empty_is_not_stamped(self) -> None:
        self.assertEqual(_aggregate_skip_why([]), WHY_NOT_STAMPED)

    def test_to_intent_uses_materialize_skip_why(self) -> None:
        mat = SegmentMaterializeResult(
            stamped=(),
            width_used=0,
            canal=None,
            extra_structure_refs=(),
            skip_why=WHY_H_LT_1,
        )
        intent = to_intent(
            _result(kind=ReliefSideKind.SHEER),
            (),
            skipped=True,
            reason=mat.skip_why or WHY_NOT_STAMPED,
            width=0,
            canal=mat.canal,
            extra_structure_refs=mat.extra_structure_refs,
        )
        self.assertEqual(intent.reason, WHY_H_LT_1)
        self.assertNotEqual(intent.reason, "clearance_skip")


if __name__ == "__main__":
    unittest.main()
