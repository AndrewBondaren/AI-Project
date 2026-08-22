"""Outgoing pack senders from a painted front and vertex bodies.

Walk + body 8-look — leftover consume slots, not SQL.
SoT: ``docs/tz_terrain_relief_consume.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from app.application.worldData.generators.terrain.relief.discover.packSenders import (
    body_pack_senders,
    walk_pack_senders,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    DiscoveredFront,
    ReliefVertices,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay, merge_grade_rim_rays


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


def pack_rays_from_vertex_bodies(
    vertices: ReliefVertices,
    z_at: Callable[[Coord], int | None],
    facing_kind: Mapping[tuple[int, Facing], ReliefSideKind],
) -> tuple[GradeRimRay, ...]:
    """Body × 8 pack senders. Painted front kind; else ``GradeRimRay.kind`` default."""
    rays: list[GradeRimRay] = []
    for slot, members in enumerate(vertices.members, start=1):
        if not members:
            continue
        for (x, y), facing in body_pack_senders(members, z_at):
            painted = facing_kind.get((slot, facing))
            rays.append(
                GradeRimRay(x=int(x), y=int(y), facing=facing)
                if painted is None
                else GradeRimRay(
                    x=int(x), y=int(y), facing=facing, kind=painted,
                )
            )
    return merge_grade_rim_rays(rays)
