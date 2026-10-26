"""Halo vs occupancy length — two different L's (R41 / R41-T-3).

Prep halo = ``max(L_tpl, envelope floor)`` so the worker can *read* a 20-cell
ramp. Occupancy cap before C41 is **L_tpl only**: envelope floor as a trace
length makes every downhill cell a seam on a small mesa.
"""

from __future__ import annotations

from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefTerrainEnvelope import ReliefOntologyEnvelopes


def _template_outward_length(templates: dict[str, ReliefTemplate]) -> int:
    cap = 1
    for tpl in templates.values():
        cap = max(cap, int(tpl.outward_length_cells()))
        for cond in tpl.conditions:
            for case in cond.cases:
                cap = max(cap, int(case.outward_length_cells()))
    return cap


def grade_halo_cells(templates: dict[str, ReliefTemplate]) -> int:
    """``max(L_tpl, envelope floor)`` across templates — not JSON-2 (R41)."""
    halo = _template_outward_length(templates) if templates else 1
    table = ReliefOntologyEnvelopes.canonical_defaults()
    for tpl in templates.values():
        for cond in tpl.conditions:
            env = table.for_terrain(cond.terrain)
            if env.applies_to(tpl.context) and env.has_slope_length_constraints():
                halo = max(halo, env.length_from_min_cells())
    return halo


def occupancy_length_cap(templates: dict[str, ReliefTemplate]) -> int | None:
    """Max k before C41 from L_tpl / case L. No pick, no envelope floor."""
    if not templates:
        return None
    return _template_outward_length(templates)


def length_cap_for_context(
    context: ReliefContext,
    templates: dict[str, ReliefTemplate],
) -> int | None:
    """Occupancy cap for one context — no pick / occurrence_seq (R41-T-3)."""
    matching = {
        uid: tpl for uid, tpl in templates.items() if tpl.context == context
    }
    return occupancy_length_cap(matching)
