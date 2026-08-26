"""Outgoing pack senders from a painted front.

Walk senders only — leftover consume slots, not SQL. Not body × 8.
SoT: ``docs/tz_terrain_relief_consume.md``.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping

from app.application.worldData.generators.terrain.relief.discover.packSenders import (
    walk_pack_senders,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    DiscoveredFront,
)
from app.application.worldData.generators.terrain.relief.validate.gradeCellRays import (
    leftover_plus_halo,
)
from app.dataModel.terrain.relief.gradeRimRay import (
    GradeRimRay,
    couple_rim_rays,
    downhill_leftover_rim_rays,
    merge_grade_rim_rays,
    pack_rim_slot_rays,
)


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


def pack_slots_for_persist(
    senders: Iterable[GradeRimRay],
    z_height_map: Mapping[tuple[int, int], int],
    *,
    cells: Collection[tuple[int, int]] | None = None,
) -> tuple[tuple[GradeRimRay, ...], tuple[tuple[int, int], ...]]:
    """Leftover + downhill fill + COUPLE. Halo from mill leftover, not COUPLE."""
    allowed = set(cells) if cells is not None else {
        (int(x), int(y)) for x, y in z_height_map
    }
    leftover = pack_rim_slot_rays(senders, cells=allowed)
    halo = leftover_plus_halo(leftover, z_height_map)
    filled = merge_grade_rim_rays(
        leftover,
        downhill_leftover_rim_rays(leftover, z_height_map),
    )
    slots = merge_grade_rim_rays(
        filled,
        couple_rim_rays(halo, filled, z_height_map),
    )
    return slots, halo
