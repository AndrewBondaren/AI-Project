"""Q2 SHEER-landing and SLOPE-corridor side geometry — not queue arbitration.

Scheduler decides leftover vs landing vs side. SoT: ``docs/tz_terrain_relief.md`` R41.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from app.application.worldData.generators.terrain.relief.discover.millCorridor import (
    CorridorLive,
)
from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    EIGHT_DELTAS,
    facing_for_delta,
    is_local_min,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    FOREIGN_MARK,
    FREE_MARK,
    Coord,
    ReliefSurface,
    ReliefVertices,
    cell_z,
)

ParentSheers = Callable[[Coord, Coord], bool]


def _hydro_blocks_seed(surface: ReliefSurface, xy: Coord) -> bool:
    role = surface.hydro_role_at(xy)
    return role is not None and role.blocks_grade_seed()


def is_slope_corridor_cell(
    xy: Coord,
    vertices: ReliefVertices,
    *,
    live: CorridorLive | None = None,
) -> bool:
    """True if ``xy`` is a committed SLOPE corridor cell during Q1/Q2.

    ``occ`` if C41 already marked it; else the live front trace (local-min
    |dz|=1 landings stay unmarked until finalize).
    """
    i = vertices.index(xy[0], xy[1])
    if i is not None:
        occ = vertices.occ[i]
        if occ != FREE_MARK and occ != FOREIGN_MARK:
            return True
    if live is not None:
        return live.is_corridor(xy)
    return False


def _is_free(vertices: ReliefVertices, xy: Coord) -> bool:
    return vertices.is_free(xy)


def enclosed_one_cell_pit(
    xy: Coord,
    surface: ReliefSurface,
    vertices: ReliefVertices,
) -> bool:
    """True if ``xy`` is a 1×1 local min fully boxed by vertex body (C41 hole)."""
    if not is_local_min(surface, xy):
        return False
    x, y = xy
    saw_parent = False
    for dx, dy in EIGHT_DELTAS:
        nb = (x + dx, y + dy)
        zn = cell_z(surface, nb)
        if zn is None:
            return False
        ni = vertices.index(nb[0], nb[1])
        if ni is None:
            return False
        if vertices.at_grid[ni] == FREE_MARK:
            return False
        saw_parent = True
    return saw_parent


def is_q2_seed(
    xy: Coord,
    surface: ReliefSurface,
    vertices: ReliefVertices,
    *,
    parent_sheers: ParentSheers,
) -> bool:
    """Q2 landing: free, 8-adjacent to a body, lower z, parent first step SHEER.

    Live ``at_grid``, not a frozen pass-1 slot set. SLOPE landings stay corridors.
    Hydro ``blocks_grade_seed`` matches side geometry.
    """
    if not _is_free(vertices, xy):
        return False
    if _hydro_blocks_seed(surface, xy):
        return False
    z = cell_z(surface, xy)
    if z is None:
        return False
    x, y = xy
    parented = False
    for dx, dy in EIGHT_DELTAS:
        nb = (x + dx, y + dy)
        ni = vertices.index(nb[0], nb[1])
        if ni is None:
            continue
        if vertices.at_grid[ni] == FREE_MARK:
            continue
        pz = cell_z(surface, nb)
        if pz is None or pz <= z:
            continue
        facing = facing_for_delta((x - nb[0], y - nb[1]))
        if facing is None:
            continue
        if parent_sheers(nb, xy):
            parented = True
            break
    if not parented:
        return False
    if enclosed_one_cell_pit(xy, surface, vertices):
        return False
    return True


def is_side_seed(
    xy: Coord,
    surface: ReliefSurface,
    vertices: ReliefVertices,
    *,
    live: CorridorLive | None = None,
) -> bool:
    """Same-z neighbor of a SLOPE corridor: free, not the floor, not a 1×1 pit.

    Queue policy (not C39 leftover, not SHEER landing) lives in the mill scheduler.
    """
    if not _is_free(vertices, xy):
        return False
    if _hydro_blocks_seed(surface, xy):
        return False
    if enclosed_one_cell_pit(xy, surface, vertices):
        return False
    if is_slope_corridor_cell(xy, vertices, live=live):
        return False
    for _nb in iter_same_z_slope_corridor_neighbors(
        xy, surface, vertices, live=live,
    ):
        return True
    return False


def iter_same_z_slope_corridor_neighbors(
    xy: Coord,
    surface: ReliefSurface,
    vertices: ReliefVertices,
    *,
    live: CorridorLive | None = None,
) -> Iterator[Coord]:
    z = cell_z(surface, xy)
    if z is None:
        return
    x, y = xy
    for dx, dy in EIGHT_DELTAS:
        nb = (x + dx, y + dy)
        ni = vertices.index(nb[0], nb[1])
        if ni is None:
            continue
        if not is_slope_corridor_cell(nb, vertices, live=live):
            continue
        zn = cell_z(surface, nb)
        if zn is None or zn != z:
            continue
        yield nb


def _corridor_owner_slot(
    xy: Coord,
    vertices: ReliefVertices,
    live: CorridorLive | None,
) -> int | None:
    i = vertices.index(xy[0], xy[1])
    if i is not None:
        occ = vertices.occ[i]
        if occ > 0:
            return int(occ)
    if live is None:
        return None
    slot = live.owner_slot(xy)
    if slot is None or int(slot) < 1:
        return None
    return int(slot)


def resolve_side_parent(
    xy: Coord,
    surface: ReliefSurface,
    vertices: ReliefVertices,
    *,
    live: CorridorLive | None = None,
) -> int | None:
    """Nearest-height SLOPE-corridor owner slot beside ``xy``, or None.

    Same corridor as ``is_side_seed``. Tie = smaller slot. FOREIGN is skipped.
    """
    z_seed = cell_z(surface, xy)
    if z_seed is None:
        return None
    best: tuple[int, int] | None = None
    for nb in iter_same_z_slope_corridor_neighbors(
        xy, surface, vertices, live=live,
    ):
        slot = _corridor_owner_slot(nb, vertices, live)
        if slot is None or slot > len(vertices.members):
            continue
        body = vertices.members[slot - 1]
        if not body:
            continue
        z_body = int(next(iter(body.values())))
        cand = (abs(z_body - int(z_seed)), slot)
        if best is None or cand < best:
            best = cand
    return None if best is None else best[1]
