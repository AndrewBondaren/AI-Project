"""Mill leftover senders from a painted front.

Walk senders only — C41 mill trace, not sidecar. Sidecar persist is
``pack_cell_slots``. Not body × 8.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping

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


def pack_slots_for_persist(
    senders: Iterable[GradeRimRay],
    z_height_map: Mapping[tuple[int, int], int],
    *,
    cells: Collection[tuple[int, int]] | None = None,
) -> tuple[tuple[GradeRimRay, ...], tuple[tuple[int, int], ...]]:
    """Locked-test leftover pack. Not FineChunkPersist. Lazy import keeps mill clean."""
    from app.application.worldData.generators.terrain.relief.validate.gradeRimPackLegacy import (
        pack_slots_for_persist as _legacy,
    )

    return _legacy(senders, z_height_map, cells=cells)
