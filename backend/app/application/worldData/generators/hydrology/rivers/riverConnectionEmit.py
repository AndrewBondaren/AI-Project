"""U18: RiverSegment → ConnectionNode/Edge DTO — no persist — D HY-4."""

from __future__ import annotations

from app.application.worldData.generators.hydrology.types import RiverSegment
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode


def emit_river_connections(
    segments: list[RiverSegment],
    *,
    world_uid: str,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    """
    Autoresolved segments only — declare edges already live in bundle import.

    v1 declare path returns empty lists.
    """
    _ = (segments, world_uid)
    return [], []
