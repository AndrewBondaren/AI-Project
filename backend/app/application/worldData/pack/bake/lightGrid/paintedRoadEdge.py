"""Painted road edge footprint — handoff RoadContributor → RoadShoulderContributor (T-31)."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy

Coord = tuple[int, int]


@dataclass(frozen=True, slots=True)
class PaintedRoadEdge:
    """One connection edge after terrain paint; shoulder grades consume this."""

    edge_uid: str
    road_cells: frozenset[Coord]
    object_policy: ObjectReliefPickPolicy | None = None
