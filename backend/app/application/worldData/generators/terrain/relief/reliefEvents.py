"""Shared relief event / why tokens — bake + grade (RELIEF-T-56 / T-66).

Canal-only WHY_* stay in ``canalAttachments``. Resolve-fallback (TZ R21) is
shared; canalAttachments re-exports ``EVENT_RESOLVE_FALLBACK`` for convenience.

T-66: ribbon skip is **three layer events** + ``why=`` discriminator (not a
monotoken). See TZ § Warn + fallback / event×why matrix.
"""

from __future__ import annotations

# --- events (relief | <event> | …) ---
# Ribbon skip layers (RELIEF-T-66) — why= always set from WHY_* below
EVENT_RIBBON_SKIP_APPLY = "ribbon_skip_apply"
EVENT_RIBBON_SKIP_GRADE = "ribbon_skip_grade"
EVENT_RIBBON_SKIP_MATERIALIZE = "ribbon_skip_materialize"
EVENT_RIBBON_GRADE_APPLY = "ribbon_grade_apply"
EVENT_RIBBON_BARRIER = "ribbon_barrier"
# TZ R21: empty pick / broken fixed uid / schedule hole / unknown canal|barrier
# ref → warn + soft fallback (generate continues). Not Mode D / not R34 skip.
EVENT_RESOLVE_FALLBACK = "resolve_fallback"
EVENT_GRADE_SKIP = "grade_skip"

# --- why / reason tokens (log field why= / reason=; Intent skip_why) ---
# apply layer (EVENT_RIBBON_SKIP_APPLY)
WHY_NO_REF_CELLS = "no_ref_cells"
WHY_NO_TEMPLATES = "no_templates"
WHY_EMPTY_SAMPLE = "empty_sample"
# grade layer (EVENT_RIBBON_SKIP_GRADE)
WHY_NO_TEMPLATE_BODY = "no_template_body"
# materialize layer (EVENT_RIBBON_SKIP_MATERIALIZE)
WHY_HEIGHT_LT_1 = "height_lt_1"
WHY_NO_EDGE_ROAD_ANCHOR = "no_edge_road_anchor"
WHY_NO_UNIQUE_OUTWARD = "no_unique_outward"
WHY_CLEARANCE_L_EFF = "clearance_L_eff"
WHY_EMPTY_PLAN = "empty_plan"
WHY_STAMP_OBSTACLE_BREAK = "stamp_obstacle_break"
WHY_STAMP_COLUMN_FAIL = "stamp_column_fail"
WHY_EMPTY_STAMP = "empty_stamp"
# Intent / aggregate (not a ribbon_skip_* log event by itself)
WHY_NOT_STAMPED = "not_stamped"
# R21 / gradePass (EVENT_RESOLVE_FALLBACK — not ribbon_skip_*)
WHY_SCHEDULE_HOLE = "schedule_hole"
# BAR-1 (EVENT_RIBBON_BARRIER)
WHY_UNKNOWN_BARRIER_REF = "unknown_barrier_ref"
WHY_EMPTY_FENCE_FOOTPRINT = "empty_fence_footprint"
WHY_NO_BARRIER_REFS = "no_barrier_refs"

# Schedule hole → safe SLOPE (TZ R21 / RELIEF-T-14), not silent skip.
REASON_SCHEDULE_HOLE_SAFE_SLOPE = "schedule_hole_safe_slope"

# Closed why sets per skip layer (tests / docs)
WHYS_RIBBON_SKIP_APPLY = frozenset({
    WHY_NO_REF_CELLS,
    WHY_NO_TEMPLATES,
    WHY_EMPTY_SAMPLE,
})
WHYS_RIBBON_SKIP_GRADE = frozenset({
    WHY_NO_TEMPLATE_BODY,
})
WHYS_RIBBON_SKIP_MATERIALIZE = frozenset({
    WHY_HEIGHT_LT_1,
    WHY_NO_EDGE_ROAD_ANCHOR,
    WHY_NO_UNIQUE_OUTWARD,
    WHY_CLEARANCE_L_EFF,
    WHY_EMPTY_PLAN,
    WHY_STAMP_OBSTACLE_BREAK,
    WHY_STAMP_COLUMN_FAIL,
    WHY_EMPTY_STAMP,
})
