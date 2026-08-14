"""Painted road edge — L0 RoadContributor footprint (light-grid cells).

Detailed ``road_shoulder`` samples meter ``road_key`` + Δz, not ``road_cells``.
``owner_uid`` is the graph edge id for a later ribbon bind.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy

Coord = tuple[int, int]


class PaintedRoadEdge(BaseModel):
    """One connection edge after L0 terrain paint.

    ``road_cells`` are light-grid ``(lx, ly)``, not fine meters.
    """

    SCHEMA_ID: ClassVar[str] = "SCH-PAINTED-ROAD-EDGE"
    model_config = ConfigDict(extra="ignore", frozen=True)

    owner_uid: str
    road_cells: frozenset[Coord]
    object_policy: ObjectReliefPickPolicy | None = None
