"""Shared relief event / why tokens — bake + grade (RELIEF-T-56).

Canal-only WHY_* stay in ``canalAttachments``. Resolve-fallback (TZ R21) is
shared; canalAttachments re-exports ``EVENT_RESOLVE_FALLBACK`` for convenience.
"""

from __future__ import annotations

# --- events (relief | <event> | …) ---
EVENT_RIBBON_SKIP = "ribbon_skip"
EVENT_RIBBON_GRADE_APPLY = "ribbon_grade_apply"
EVENT_RIBBON_BARRIER = "ribbon_barrier"
# TZ R21: empty pick / broken fixed uid / schedule hole / unknown canal|barrier
# ref → warn + soft fallback (generate continues). Not Mode D / not R34 skip.
EVENT_RESOLVE_FALLBACK = "resolve_fallback"
EVENT_GRADE_SKIP = "grade_skip"

# --- why / reason tokens ---
WHY_NO_EDGE_ROAD_ANCHOR = "no_edge_road_anchor"
WHY_SCHEDULE_HOLE = "schedule_hole"
WHY_NOT_STAMPED = "not_stamped"
WHY_NO_TEMPLATE_BODY = "no_template_body"
WHY_EMPTY_SAMPLE = "empty_sample"
WHY_NO_REF_CELLS = "no_ref_cells"
WHY_NO_TEMPLATES = "no_templates"
WHY_STAMP_OBSTACLE_BREAK = "stamp_obstacle_break"
WHY_STAMP_COLUMN_FAIL = "stamp_column_fail"
WHY_EMPTY_STAMP = "empty_stamp"
WHY_EMPTY_PLAN = "empty_plan"
WHY_HEIGHT_LT_1 = "height_lt_1"
WHY_UNKNOWN_BARRIER_REF = "unknown_barrier_ref"
WHY_EMPTY_FENCE_FOOTPRINT = "empty_fence_footprint"
WHY_NO_BARRIER_REFS = "no_barrier_refs"

# Schedule hole → safe SLOPE (TZ R21 / RELIEF-T-14), not silent skip.
REASON_SCHEDULE_HOLE_SAFE_SLOPE = "schedule_hole_safe_slope"
