"""Normalize Mode A|B wire → ReliefDeltaSchedule (I8)."""

from __future__ import annotations

from app.dataModel.terrain.relief.enums import ReliefSlopePolicy
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


def _knobs_from_case(case: ReliefRoleCase) -> ReliefDeltaInterval:
    return ReliefDeltaInterval(
        value_min=0,
        value_max=None,
        slope_weight=float(case.slope_weight or 0.0),
        sheer_weight=float(case.sheer_weight or 0.0),
        shoulder_width_cells=case.shoulder_width_cells,
        earthen_canal=case.earthen_canal,
        structure_refs=tuple(case.structure_refs),
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
        none_knobs=_knobs_from_case(none_case),
        down=(ReliefDeltaInterval(
            value_min=down_min,
            value_max=None,
            slope_weight=float(down_case.slope_weight or 0.0),
            sheer_weight=float(down_case.sheer_weight or 0.0),
            shoulder_width_cells=down_case.shoulder_width_cells,
            earthen_canal=down_case.earthen_canal,
            structure_refs=tuple(down_case.structure_refs),
        ),),
        up=(ReliefDeltaInterval(
            value_min=up_min,
            value_max=None,
            slope_weight=float(up_case.slope_weight or 0.0),
            sheer_weight=float(up_case.sheer_weight or 0.0),
            shoulder_width_cells=up_case.shoulder_width_cells,
            earthen_canal=up_case.earthen_canal,
            structure_refs=tuple(up_case.structure_refs),
        ),),
    )


def _normalize_mode_b(
    none_case: ReliefRoleCase,
    down_case: ReliefRoleCase,
    up_case: ReliefRoleCase,
) -> ReliefDeltaSchedule:
    down = tuple(
        ReliefDeltaInterval(
            value_min=b.delta_z_min,
            value_max=b.delta_z_max,
            slope_weight=b.slope_weight,
            sheer_weight=b.sheer_weight,
            shoulder_width_cells=b.shoulder_width_cells,
            earthen_canal=b.earthen_canal,
            structure_refs=tuple(b.structure_refs),
        )
        for b in (down_case.bands or [])
    )
    up = tuple(
        ReliefDeltaInterval(
            value_min=b.delta_z_min,
            value_max=b.delta_z_max,
            slope_weight=b.slope_weight,
            sheer_weight=b.sheer_weight,
            shoulder_width_cells=b.shoulder_width_cells,
            earthen_canal=b.earthen_canal,
            structure_refs=tuple(b.structure_refs),
        )
        for b in (up_case.bands or [])
    )
    return ReliefDeltaSchedule(
        none_max_abs=0,  # Mode B: abs(dz) < 1 → none
        none_knobs=None,
        down=down,
        up=up,
    )
