"""Sender keys from the vertex 8-look and lockstep walk.

Geometry only: ``(cell, Facing)``. Pack POJO / kind / persist live in refine.
Equal-z is unified-surface coupling, not a leftover sender.
SoT: ``docs/tz_terrain_relief_consume.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    iter_body_eight_views,
)
from app.application.worldData.generators.terrain.relief.discover.types import Coord
from app.dataModel.spatial.facing import Facing


def body_pack_senders(
    body: Mapping[Coord, int],
    z_at: Callable[[Coord], int | None],
) -> tuple[tuple[Coord, Facing], ...]:
    """Downhill leftover senders from the body × 8 loop. Equal-z / uphill skipped."""
    out: list[tuple[Coord, Facing]] = []
    seen: set[tuple[int, int, Facing]] = set()
    for src, facing, _nb, z_src, zn in iter_body_eight_views(body, z_at):
        if zn >= z_src:
            continue
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
    """Outward leftover on each lockstep cell. Equal-z along width is coupling."""
    seen: set[tuple[int, int, Facing]] = set()
    out: list[tuple[Coord, Facing]] = []
    for x, y in (*rim, *corridor):
        xy = (int(x), int(y))
        key = (xy[0], xy[1], outward)
        if key in seen:
            continue
        seen.add(key)
        out.append((xy, outward))
    return tuple(out)
