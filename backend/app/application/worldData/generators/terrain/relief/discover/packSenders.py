"""Sender keys from the lockstep walk.

Geometry only: ``(cell, Facing)``. Pack POJO / kind / persist live in refine.
Equal-z is unified-surface coupling, not a leftover sender.
SoT: ``docs/tz_terrain_relief_consume.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.generators.terrain.relief.discover.types import Coord
from app.dataModel.spatial.facing import Facing


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
