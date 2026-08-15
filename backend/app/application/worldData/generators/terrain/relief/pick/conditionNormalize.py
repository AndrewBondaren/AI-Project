"""Normalize Mode A|B wire → ReliefDeltaSchedule (I8).

RELIEF-T-33: one knobs→interval builder. RELIEF-T-39: no silent ``or`` fallbacks —
Mode A fields come from validated POJO / ``mode_a_grade_knobs()``.
"""

from __future__ import annotations

from app.dataModel.terrain.relief.enums import ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefDeltaSchedule import (
    ReliefDeltaInterval,
    ReliefDeltaSchedule,
)
from app.dataModel.terrain.relief.reliefGradeKnobs import ReliefGradeKnobs
from app.dataModel.terrain.relief.reliefRoleCase import ReliefRoleCase
from app.dataModel.terrain.relief.reliefTerrainCondition import ReliefTerrainCondition


def normalize_condition(condition: ReliefTerrainCondition) -> ReliefDeltaSchedule:
    """Wire A|B → single schedule. Consumers must not branch on mode."""
    none_case = condition.case_for(ReliefSlopePolicy.SLOPE_NONE)
    down_case = condition.case_for(ReliefSlopePolicy.SLOPE_DOWN)
    up_case = condition.case_for(ReliefSlopePolicy.SLOPE_UP)

    if condition.is_mode_a:
        return _normalize_mode_a(none_case, down_case, up_case)
    return _normalize_mode_b(none_case, down_case, up_case)


def _interval_from_grade_knobs(
    knobs: ReliefGradeKnobs,
    *,
    value_min: int,
    value_max: int | None = None,
) -> ReliefDeltaInterval:
    """Map validated grade knobs → runtime interval (shared Mode A|B)."""
    return ReliefDeltaInterval(
        value_min=value_min,
        value_max=value_max,
        slope_weight=float(knobs.slope_weight),
        sheer_weight=float(knobs.sheer_weight),
        slope_length_cells=knobs.slope_length_cells,
        target_angle_deg=knobs.target_angle_deg,
        earthen_canal=knobs.earthen_canal,
        structure_canal=knobs.structure_canal,
        structure_refs=tuple(knobs.structure_refs),
    )


def _normalize_mode_a(
    none_case: ReliefRoleCase,
    down_case: ReliefRoleCase,
    up_case: ReliefRoleCase,
) -> ReliefDeltaSchedule:
    # Mode A POJO guarantees delta_z is set (no silent 0/1)
    none_max = int(none_case.delta_z)  # type: ignore[arg-type]
    down_min = int(down_case.delta_z)  # type: ignore[arg-type]
    up_min = int(up_case.delta_z)  # type: ignore[arg-type]
    return ReliefDeltaSchedule(
        none_max_abs=none_max,
        none_knobs=_interval_from_grade_knobs(
            none_case.mode_a_grade_knobs(),
            value_min=0,
        ),
        down=(_interval_from_grade_knobs(
            down_case.mode_a_grade_knobs(),
            value_min=down_min,
        ),),
        up=(_interval_from_grade_knobs(
            up_case.mode_a_grade_knobs(),
            value_min=up_min,
        ),),
    )


def _normalize_mode_b(
    none_case: ReliefRoleCase,
    down_case: ReliefRoleCase,
    up_case: ReliefRoleCase,
) -> ReliefDeltaSchedule:
    del none_case  # Mode B: none_max_abs=0; knobs unused
    assert down_case.bands is not None and up_case.bands is not None
    down = tuple(
        _interval_from_grade_knobs(
            band,
            value_min=band.delta_z_min,
            value_max=band.delta_z_max,
        )
        for band in down_case.bands
    )
    up = tuple(
        _interval_from_grade_knobs(
            band,
            value_min=band.delta_z_min,
            value_max=band.delta_z_max,
        )
        for band in up_case.bands
    )
    return ReliefDeltaSchedule(
        none_max_abs=0,
        none_knobs=None,
        down=down,
        up=up,
    )
