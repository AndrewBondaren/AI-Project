"""Painted road edge footprint — RoadContributor handoff for detailed shoulder (T-31 / R36u-T-10)."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy

Coord = tuple[int, int]


@dataclass(frozen=True, slots=True)
class PaintedRoadEdge:
    """One connection edge after terrain paint; detailed ``road_shoulder`` will consume this.

    ``owner_uid`` = ``ConnectionEdge.edge_uid`` (road graph), used as ribbon owner.
    """

    owner_uid: str
    road_cells: frozenset[Coord]
    object_policy: ObjectReliefPickPolicy | None = None
