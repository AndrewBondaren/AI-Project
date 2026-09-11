"""Plot xy×z collision — only when a district has more than one deck (ярус)."""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import (
    AreaSlot,
    z_range,
)


def district_has_multiple_decks(slots: Sequence[AreaSlot]) -> bool:
    return len({slot.deck for slot in slots}) >= 2


def plots_overlap_xy(a: AreaSlot, b: AreaSlot) -> bool:
    if not a.cells or not b.cells:
        return False
    return not set(a.cells).isdisjoint(b.cells)


def plots_overlap_z(a: AreaSlot, b: AreaSlot) -> bool:
    lo_a, hi_a = z_range(a)
    lo_b, hi_b = z_range(b)
    return lo_a < hi_b and lo_b < hi_a


def plot_z_collisions(slots: Sequence[AreaSlot]) -> list[tuple[int, int]]:
    """Pairs of indices whose xy and z intervals overlap.

    No-op when the district has a single ярус (today: recipe ``deck=0``,
    every plot copies it).
    """
    if not district_has_multiple_decks(slots):
        return []
    hits: list[tuple[int, int]] = []
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            if plots_overlap_xy(slots[i], slots[j]) and plots_overlap_z(slots[i], slots[j]):
                hits.append((i, j))
    return hits
