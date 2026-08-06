"""Shared relief event / why tokens — bake + grade (RELIEF-T-56).

Canal-only WHY_* stay in ``canalAttachments``. ``EVENT_R21_FALLBACK`` is shared
(R21) and re-exported from canalAttachments for existing imports.
"""

from __future__ import annotations

# --- events (relief | <event> | …) ---
EVENT_RIBBON_SKIP = "ribbon_skip"
EVENT_RIBBON_GRADE_APPLY = "ribbon_grade_apply"
EVENT_ROAD_SHOULDER_BARRIER = "road_shoulder_barrier"
EVENT_R21_FALLBACK = "r21_fallback"
EVENT_GRADE_SKIP = "grade_skip"

# Legacy alias — shared ribbon path (road_shoulder / open_land / shore).
EVENT_ROAD_SHOULDER_SKIP = EVENT_RIBBON_SKIP

# --- why / reason tokens ---
WHY_NO_EDGE_ROAD_ANCHOR = "no_edge_road_anchor"
WHY_SCHEDULE_HOLE = "schedule_hole"
WHY_NOT_STAMPED = "not_stamped"
WHY_NO_TEMPLATE_BODY = "no_template_body"
WHY_EMPTY_SAMPLE = "empty_sample"
WHY_NO_REF_CELLS = "no_ref_cells"
WHY_NO_ROAD_CELLS = WHY_NO_REF_CELLS  # legacy alias
WHY_NO_TEMPLATES = "no_templates"
WHY_STAMP_OBSTACLE_BREAK = "stamp_obstacle_break"
WHY_STAMP_COLUMN_FAIL = "stamp_column_fail"
WHY_EMPTY_STAMP = "empty_stamp"
WHY_EMPTY_PLAN = "empty_plan"
WHY_H_LT_1 = "h_lt_1"
WHY_UNKNOWN_BARRIER_REF = "unknown_barrier_ref"
WHY_EMPTY_FENCE_FOOTPRINT = "empty_fence_footprint"
WHY_NO_BARRIER_REFS = "no_barrier_refs"

REASON_SCHEDULE_HOLE_R21_SLOPE = "schedule_hole_r21_slope"
