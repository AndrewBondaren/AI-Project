"""Unit: RELIEF-T-56 event tokens + RELIEF-T-60/T-66 ribbon skip layers.

L0 apply silent-path tests removed with outdoor ribbon (R36u-T-8).
"""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief import canalAttachments
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_RESOLVE_FALLBACK,
    EVENT_RIBBON_BARRIER,
    EVENT_RIBBON_SKIP_APPLY,
    EVENT_RIBBON_SKIP_GRADE,
    EVENT_RIBBON_SKIP_MATERIALIZE,
    REASON_SCHEDULE_HOLE_SAFE_SLOPE,
    WHY_CLEARANCE_L_EFF,
    WHY_EMPTY_SAMPLE,
    WHY_HEIGHT_LT_1,
    WHY_NO_EDGE_ROAD_ANCHOR,
    WHY_NO_REF_CELLS,
    WHY_NO_TEMPLATES,
    WHY_NO_UNIQUE_OUTWARD,
    WHY_NOT_STAMPED,
    WHY_SCHEDULE_HOLE,
    WHYS_RIBBON_SKIP_APPLY,
    WHYS_RIBBON_SKIP_GRADE,
    WHYS_RIBBON_SKIP_MATERIALIZE,
)


class ReliefEventsTokensTest(unittest.TestCase):
    def test_shared_resolve_fallback_reexported_from_canal(self) -> None:
        self.assertEqual(canalAttachments.EVENT_RESOLVE_FALLBACK, EVENT_RESOLVE_FALLBACK)
        self.assertEqual(EVENT_RESOLVE_FALLBACK, "resolve_fallback")
        self.assertEqual(EVENT_RIBBON_BARRIER, "ribbon_barrier")
        self.assertEqual(WHY_SCHEDULE_HOLE, "schedule_hole")
        self.assertEqual(REASON_SCHEDULE_HOLE_SAFE_SLOPE, "schedule_hole_safe_slope")
        self.assertEqual(WHY_HEIGHT_LT_1, "height_lt_1")
        self.assertEqual(WHY_NO_EDGE_ROAD_ANCHOR, "no_edge_road_anchor")
        self.assertEqual(WHY_NOT_STAMPED, "not_stamped")
        self.assertEqual(EVENT_RIBBON_SKIP_APPLY, "ribbon_skip_apply")
        self.assertEqual(EVENT_RIBBON_SKIP_GRADE, "ribbon_skip_grade")
        self.assertEqual(EVENT_RIBBON_SKIP_MATERIALIZE, "ribbon_skip_materialize")
        self.assertEqual(WHY_NO_REF_CELLS, "no_ref_cells")
        self.assertEqual(WHY_NO_UNIQUE_OUTWARD, "no_unique_outward")
        self.assertEqual(WHY_CLEARANCE_L_EFF, "clearance_L_eff")
        self.assertEqual(WHY_EMPTY_SAMPLE, "empty_sample")

    def test_t66_why_sets_closed(self) -> None:
        self.assertEqual(
            WHYS_RIBBON_SKIP_APPLY,
            frozenset({WHY_NO_REF_CELLS, WHY_NO_TEMPLATES, WHY_EMPTY_SAMPLE}),
        )
        self.assertEqual(WHYS_RIBBON_SKIP_GRADE, frozenset({"no_template_body"}))
        self.assertIn(WHY_CLEARANCE_L_EFF, WHYS_RIBBON_SKIP_MATERIALIZE)
        self.assertIn(WHY_NO_UNIQUE_OUTWARD, WHYS_RIBBON_SKIP_MATERIALIZE)


if __name__ == "__main__":
    unittest.main()
