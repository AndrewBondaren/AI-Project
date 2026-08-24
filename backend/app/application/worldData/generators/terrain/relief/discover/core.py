"""Discover orchestrator — Q1 C39, Q2 SHEER landing, Q3 SLOPE-corridor side.

One mill after each seed. Stages own geometry. Does not write z/uid or fill columns.
SoT: ``docs/tz_terrain_relief.md`` R41.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from app.application.worldData.generators.terrain.relief.discover.apron import (
    is_q2_seed,
    is_q3_seed,
    is_slope_corridor_cell,
    resolve_q3_parent,
)
from app.application.worldData.generators.terrain.relief.discover.fronts import FrontStage
from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    facing_for_delta,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    VertexBodyPlugin,
)
from app.application.worldData.generators.terrain.relief.discover.rim import (
    RimStage,
    seed_rim,
)
from app.application.worldData.generators.terrain.relief.discover.seam import SeamStage
from app.application.worldData.generators.terrain.relief.discover.types import (
    CapFront,
    CellBlocked,
    Coord,
    FrontGeometry,
    ReliefSurface,
    ReliefVertices,
    cell_z,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.reliefTerrainEnvelope import ReliefOntologyEnvelopes

__all__ = ["discover_fronts", "reconcile_members", "seed_rim"]


def reconcile_members(vertices: ReliefVertices) -> None:
    """C38: drop body cells that landed in another vertex's corridor."""
    for slot, members in enumerate(vertices.members, start=1):
        drop: list[Coord] = []
        for xy in members:
            i = vertices.index(xy[0], xy[1])
            if i is None or vertices.at_grid[i] != slot:
                drop.append(xy)
                continue
            occ = vertices.occ[i]
            if occ != 0 and occ != slot:
                drop.append(xy)
                vertices.at_grid[i] = 0
        for xy in drop:
            members.pop(xy, None)


def _seed_one(
    *,
    rim: RimStage,
    front: FrontStage,
    seam: SeamStage,
    vertices: ReliefVertices,
    xy: Coord,
    fronts: list[FrontGeometry],
) -> int | None:
    plugin = rim.plugin_for(xy)
    if plugin is None:
        return None
    body = rim.flood(xy, plugin)
    def _in_trace(cell: Coord) -> bool:
        return any(cell in item.corridor for item in fronts)
    body = {
        cell: z for cell, z in body.items()
        if not is_slope_corridor_cell(cell, vertices, in_slope_trace=_in_trace)
    }
    if not body:
        return None
    slot = vertices.add_vertex(body)
    traces = front.propose(slot, body, plugin)
    fronts.extend(seam.commit(traces, plugin))
    return slot


def _drain(
    *,
    rim: RimStage,
    front: FrontStage,
    seam: SeamStage,
    vertices: ReliefVertices,
    fronts: list[FrontGeometry],
    is_seed: Callable[[Coord], bool],
    loop: bool,
    on_seeded: Callable[[int, Coord], None] | None = None,
) -> None:
    """High→low scan; ``loop`` repeats while a pass adds a vertex (Q3)."""

    def _pass() -> bool:
        n_before = len(vertices.members)
        for _z, cells in rim.buckets_high_to_low():
            for xy in cells:
                if not is_seed(xy):
                    continue
                slot = _seed_one(
                    rim=rim, front=front, seam=seam, vertices=vertices,
                    xy=xy, fronts=fronts,
                )
                if slot is not None and on_seeded is not None:
                    on_seeded(slot, xy)
        return len(vertices.members) > n_before

    if loop:
        while _pass():
            pass
        return
    _pass()


def discover_fronts(
    surface: ReliefSurface,
    *,
    origin_x: int,
    origin_y: int,
    width: int,
    height: int,
    plugins: Sequence[VertexBodyPlugin],
    cell_blocked: CellBlocked,
    existing_uids: dict[Coord, str] | None = None,
    cap_front: CapFront | None = None,
    envelopes: ReliefOntologyEnvelopes | None = None,
) -> tuple[ReliefVertices, tuple[FrontGeometry, ...]]:
    """Q1 C39 → Q2 SHEER apron → Q3 SLOPE-side loop → SHEER traces → C41 → C38."""
    vertices = ReliefVertices.for_bounds(
        origin_x=int(origin_x),
        origin_y=int(origin_y),
        width=int(width),
        height=int(height),
    )
    if existing_uids:
        for xy in existing_uids:
            vertices.mark_foreign(xy)
    if not plugins:
        return vertices, ()

    rim = RimStage(surface, vertices, plugins)
    front = FrontStage(surface, vertices, cell_blocked, cap_front, envelopes)
    seam = SeamStage(vertices, surface)
    fronts: list[FrontGeometry] = []

    def _parent_sheers(parent: Coord, landing: Coord) -> bool:
        plugin = rim.plugin_for(parent)
        if plugin is None:
            return False
        if not plugin.may_shoot(parent, landing, surface):
            return False
        facing = facing_for_delta(
            (landing[0] - parent[0], landing[1] - parent[1]),
        )
        if facing is None:
            return False
        pz = cell_z(surface, parent)
        lz = cell_z(surface, landing)
        if pz is None or lz is None:
            return False
        return front.first_step_outcome(parent, facing, plugin, pz - lz) == ReliefSideKind.SHEER

    def _q2(xy: Coord) -> bool:
        return is_q2_seed(xy, surface, vertices, parent_sheers=_parent_sheers)

    def _in_slope_trace(nb: Coord) -> bool:
        return any(nb in item.corridor for item in fronts)

    def _q3(xy: Coord) -> bool:
        return is_q3_seed(
            xy,
            surface,
            vertices,
            parent_sheers=_parent_sheers,
            in_slope_corridor=_in_slope_trace,
        )

    def _live_corridor_slot(cell: Coord) -> int | None:
        for item in fronts:
            if cell in item.corridor:
                return int(item.slot)
        return None

    def _record_q3(slot: int, xy: Coord) -> None:
        parent = resolve_q3_parent(
            xy,
            surface,
            vertices,
            in_slope_corridor=_in_slope_trace,
            corridor_slot=_live_corridor_slot,
        )
        if parent is None or parent == slot:
            return
        vertices.q3_parent[slot] = parent

    mill = dict(rim=rim, front=front, seam=seam, vertices=vertices, fronts=fronts)
    _drain(**mill, is_seed=rim.is_seed, loop=False)
    _drain(**mill, is_seed=_q2, loop=False)
    _drain(**mill, is_seed=_q3, loop=True, on_seeded=_record_q3)
    for slot, body in enumerate(vertices.members, start=1):
        if not body:
            continue
        plugin = rim.plugin_for(next(iter(body)))
        if plugin is None:
            continue
        traces = front.propose_sheers(slot, body, plugin)
        fronts.extend(seam.commit(traces, plugin))
    fronts = list(seam.finalize(fronts))
    reconcile_members(vertices)
    return vertices, tuple(fronts)
