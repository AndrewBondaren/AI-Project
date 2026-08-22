"""Sender keys from the vertex 8-look and lockstep walk.

Geometry only: ``(cell, Facing)``. Pack POJO / kind / persist live in refine.
SoT: ``docs/tz_terrain_relief_consume.md``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    facing_for_delta,
    iter_body_eight_views,
    step_k,
)
from app.application.worldData.generators.terrain.relief.discover.types import Coord
from app.dataModel.spatial.facing import Facing, opposite

# One sender per equal-z undirected edge (the other end is persist receiver).
_EQUAL_OWNER_FACINGS: frozenset[Facing] = frozenset({
    Facing.NORTH,
    Facing.NORTHEAST,
    Facing.EAST,
    Facing.SOUTHEAST,
})


def _owns_equal_edge(facing: Facing) -> bool:
    return facing in _EQUAL_OWNER_FACINGS


def body_pack_senders(
    body: Mapping[Coord, int],
    z_at: Callable[[Coord], int | None],
) -> tuple[tuple[Coord, Facing], ...]:
    """Senders from the same body × 8 loop as leftover rim shots."""
    members = {(int(x), int(y)) for x, y in body}
    out: list[tuple[Coord, Facing]] = []
    seen: set[tuple[int, int, Facing]] = set()
    for src, facing, nb, z_src, zn in iter_body_eight_views(body, z_at):
        if zn < z_src:
            key = (src[0], src[1], facing)
        elif zn > z_src:
            continue
        elif nb in members and not _owns_equal_edge(facing):
            continue
        else:
            key = (src[0], src[1], facing)
        if key in seen:
            continue
        seen.add(key)
        out.append((src, facing))
    return tuple(out)


def walk_pack_senders(
    rim: Sequence[Coord],
    corridor: Sequence[Coord],
    outward: Facing,
) -> tuple[tuple[Coord, Facing], ...]:
    """Outward sender on each lockstep cell, plus equal-z edges along width W."""
    rim_cells = tuple((int(x), int(y)) for x, y in rim)
    corridor_cells = tuple((int(x), int(y)) for x, y in corridor)
    seen: set[tuple[int, int, Facing]] = set()
    out: list[tuple[Coord, Facing]] = []

    def add(xy: Coord, facing: Facing) -> None:
        key = (xy[0], xy[1], facing)
        if key in seen:
            return
        seen.add(key)
        out.append((xy, facing))

    for xy in (*rim_cells, *corridor_cells):
        add(xy, outward)

    by_k: dict[int, list[Coord]] = defaultdict(list)
    for xy in rim_cells:
        by_k[0].append(xy)
    for xy in corridor_cells:
        k = step_k(xy, rim_cells, outward)
        by_k[1 if k is None else k].append(xy)

    for cells in by_k.values():
        uniq = list(dict.fromkeys(cells))
        uniq.sort()
        for a, b in zip(uniq, uniq[1:]):
            delta = (b[0] - a[0], b[1] - a[1])
            if max(abs(delta[0]), abs(delta[1])) != 1:
                continue
            facing = facing_for_delta(delta)
            if facing is None:
                continue
            if _owns_equal_edge(facing):
                add(a, facing)
            else:
                add(b, opposite(facing))
    return tuple(out)
