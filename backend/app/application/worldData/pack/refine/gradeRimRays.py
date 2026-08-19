"""Outgoing rim rays from a painted ``DiscoveredFront`` — leftover consume, not SQL."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.discover.types import (
    DiscoveredFront,
)
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay


def rim_rays_from_front(front: DiscoveredFront) -> tuple[GradeRimRay, ...]:
    """One ray per rim cell × this front's outward Facing and kind."""
    decision = front.spec.decision
    kind = decision.kind
    if kind is None or decision.skipped:
        return ()
    facing = front.spec.outward
    return tuple(
        GradeRimRay(x=int(x), y=int(y), facing=facing, kind=kind)
        for x, y in front.rim
    )
