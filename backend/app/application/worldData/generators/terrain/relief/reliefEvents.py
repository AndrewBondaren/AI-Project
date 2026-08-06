"""Shared relief event / why tokens — bake + grade (RELIEF-T-56).

Canal-only WHY_* stay in ``canalAttachments``. ``EVENT_R21_FALLBACK`` is shared
(R21) and re-exported from canalAttachments for existing imports.
"""

from __future__ import annotations

# --- events (relief | <event> | …) ---
EVENT_ROAD_SHOULDER_SKIP = "road_shoulder_skip"
EVENT_R21_FALLBACK = "r21_fallback"
EVENT_GRADE_SKIP = "grade_skip"

# --- why / reason tokens ---
WHY_NO_EDGE_ROAD_ANCHOR = "no_edge_road_anchor"
WHY_SCHEDULE_HOLE = "schedule_hole"
WHY_NOT_STAMPED = "not_stamped"
WHY_NO_TEMPLATE_BODY = "no_template_body"
WHY_EMPTY_SAMPLE = "empty_sample"
WHY_NO_ROAD_CELLS = "no_road_cells"
WHY_NO_TEMPLATES = "no_templates"
WHY_STAMP_OBSTACLE_BREAK = "stamp_obstacle_break"
WHY_STAMP_COLUMN_FAIL = "stamp_column_fail"
WHY_EMPTY_STAMP = "empty_stamp"
WHY_EMPTY_PLAN = "empty_plan"
WHY_H_LT_1 = "h_lt_1"

REASON_SCHEDULE_HOLE_R21_SLOPE = "schedule_hole_r21_slope"
