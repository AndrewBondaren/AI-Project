"""Outgoing pack senders from a painted front.

Walk senders only — leftover consume slots, not SQL. Not body × 8.
SoT: ``docs/tz_terrain_relief_consume.md``.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.discover.packSenders import (
    walk_pack_senders,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    DiscoveredFront,
)
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay


def rim_rays_from_front(front: DiscoveredFront) -> tuple[GradeRimRay, ...]:
    """Lockstep leftover senders: rim ∪ corridor × outward only."""
    decision = front.spec.decision
    kind = decision.kind
    if kind is None or decision.skipped:
        return ()
    facing = front.spec.outward
    return tuple(
        GradeRimRay(x=int(x), y=int(y), facing=slot_facing, kind=kind)
        for (x, y), slot_facing in walk_pack_senders(
            front.rim, front.spec.corridor, facing,
        )
    )
