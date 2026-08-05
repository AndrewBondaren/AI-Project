"""Normalize Mode A|B wire → ReliefDeltaSchedule (I8)."""

from __future__ import annotations

from app.dataModel.terrain.relief.enums import ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefDeltaBand import ReliefDeltaBand
from app.dataModel.terrain.relief.reliefDeltaSchedule import (
    ReliefDeltaInterval,
    ReliefDeltaSchedule,
)
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


def _knobs_from_case(case: ReliefRoleCase, *, value_min: int) -> ReliefDeltaInterval:
    return ReliefDeltaInterval(
        value_min=value_min,
        value_max=None,
        slope_weight=float(case.slope_weight or 0.0),
        sheer_weight=float(case.sheer_weight or 0.0),
        slope_length_cells=case.slope_length_cells,
        target_angle_deg=case.target_angle_deg,
        earthen_canal=case.earthen_canal,
        structure_canal=case.structure_canal,
        structure_refs=tuple(case.structure_refs),
    )


def _knobs_from_band(band: ReliefDeltaBand) -> ReliefDeltaInterval:
    return ReliefDeltaInterval(
        value_min=band.delta_z_min,
        value_max=band.delta_z_max,
        slope_weight=band.slope_weight,
        sheer_weight=band.sheer_weight,
        slope_length_cells=band.slope_length_cells,
        target_angle_deg=band.target_angle_deg,
        earthen_canal=band.earthen_canal,
        structure_canal=band.structure_canal,
        structure_refs=tuple(band.structure_refs),
    )


def _normalize_mode_a(
    none_case: ReliefRoleCase,
    down_case: ReliefRoleCase,
    up_case: ReliefRoleCase,
) -> ReliefDeltaSchedule:
    none_max = int(none_case.delta_z or 0)
    down_min = int(down_case.delta_z or 1)
    up_min = int(up_case.delta_z or 1)
    return ReliefDeltaSchedule(
        none_max_abs=none_max,
        none_knobs=_knobs_from_case(none_case, value_min=0),
        down=(_knobs_from_case(down_case, value_min=down_min),),
        up=(_knobs_from_case(up_case, value_min=up_min),),
    )


def _normalize_mode_b(
    none_case: ReliefRoleCase,
    down_case: ReliefRoleCase,
    up_case: ReliefRoleCase,
) -> ReliefDeltaSchedule:
    del none_case  # Mode B: none_max_abs=0; knobs unused
    down = tuple(_knobs_from_band(b) for b in (down_case.bands or []))
    up = tuple(_knobs_from_band(b) for b in (up_case.bands or []))
    return ReliefDeltaSchedule(
        none_max_abs=0,
        none_knobs=None,
        down=down,
        up=up,
    )
