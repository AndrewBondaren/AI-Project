"""Resolve C22 plot token N and planting priority — tz_structure_connections.md §5.1.3."""

from __future__ import annotations

from app.dataModel.locations.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.locations.structure.building.plotLayoutTemplate import DrawingKey

# SoT fallbacks when no map key exists (not Field defaults on the maps).
COUNT_WITHOUT_KEY = 1
PRIORITY_WITHOUT_KEY = 0

N_FROM_REQUIRED = "required"
N_FROM_DISTRICT = "district"
N_FROM_SETTLEMENT = "settlement"
N_FROM_DEFAULT = "default"


def resolve_plot_count(
    template_uid: str,
    *,
    required: RequiredStructure | None,
    district_counts: dict[DrawingKey, int] | None,
    settlement_counts: dict[DrawingKey, int] | None,
) -> tuple[int, str]:
    """
    First set source: required.count → district plot_counts → settlement plot_counts → 1.
    Missing key is not zero. Explicit 0 is zero. Required ignores plot_counts.
    Map keys are plot member uids (tz_city_generation §9.2/§9.4).
    """
    if required is not None:
        return int(required.count), N_FROM_REQUIRED
    if district_counts is not None and template_uid in district_counts:
        return int(district_counts[template_uid]), N_FROM_DISTRICT
    if settlement_counts is not None and template_uid in settlement_counts:
        return int(settlement_counts[template_uid]), N_FROM_SETTLEMENT
    return COUNT_WITHOUT_KEY, N_FROM_DEFAULT


def resolve_plot_priority(
    template_uid: str,
    *,
    district_priority: dict[DrawingKey, int] | None,
    settlement_priority: dict[DrawingKey, int] | None,
) -> int:
    """District plot_priority by uid key → settlement map by uid key → 0 (pass 2)."""
    if district_priority is not None and template_uid in district_priority:
        return int(district_priority[template_uid])
    if settlement_priority is not None and template_uid in settlement_priority:
        return int(settlement_priority[template_uid])
    return PRIORITY_WITHOUT_KEY
