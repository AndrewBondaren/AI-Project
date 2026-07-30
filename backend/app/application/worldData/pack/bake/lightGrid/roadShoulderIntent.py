"""Bake-boundary road_shoulder intent (RELIEF-T-24 / BAR-1).

Neutral DTO for ``LightGridBakeContext`` — no generator grade types.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoadShoulderIntent:
    """Data-out after shoulder grade/stamp; barrier materialize = RELIEF-BAR-1."""

    edge_uid: str
    site_id: str
    template_uid: str | None
    kind: str | None
    width: int
    cell_coords: tuple[tuple[int, int], ...]
    earthen_canal: bool
    structure_refs: tuple[str, ...]
    skipped: bool
    reason: str = ""
