"""Resolve C22 plot token N and planting priority — tz_structure_connections.md §5.1.3."""

from __future__ import annotations

from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.structure.building.buildingLayoutTemplate import DrawingKey

# SoT fallbacks when no map key exists (not Field defaults on the maps).
COUNT_WITHOUT_KEY = 1
PRIORITY_WITHOUT_KEY = 0

N_FROM_REQUIRED = "required"
N_FROM_DISTRICT = "district"
N_FROM_SETTLEMENT = "settlement"
N_FROM_DEFAULT = "default"


def resolve_plot_count(
    system_name: str,
    *,
    required: RequiredStructure | None,
    district_counts: dict[DrawingKey, int] | None,
    settlement_counts: dict[DrawingKey, int] | None,
) -> tuple[int, str]:
    """
    First set source: required.count → district plot_counts → settlement plot_counts → 1.
    Missing key is not zero. Explicit 0 is zero. Required ignores plot_counts.
    """
    if required is not None:
        return int(required.count), N_FROM_REQUIRED
    if district_counts is not None and system_name in district_counts:
        return int(district_counts[system_name]), N_FROM_DISTRICT
    if settlement_counts is not None and system_name in settlement_counts:
        return int(settlement_counts[system_name]), N_FROM_SETTLEMENT
    return COUNT_WITHOUT_KEY, N_FROM_DEFAULT


def resolve_plot_priority(
    system_name: str,
    *,
    district_priority: dict[DrawingKey, int] | None,
    settlement_priority: dict[DrawingKey, int] | None,
) -> int:
    """District plot_priority by key → settlement map by key → 0 (pass 2)."""
    if district_priority is not None and system_name in district_priority:
        return int(district_priority[system_name])
    if settlement_priority is not None and system_name in settlement_priority:
        return int(settlement_priority[system_name])
    return PRIORITY_WITHOUT_KEY
