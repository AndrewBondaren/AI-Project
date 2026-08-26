"""Q1 leftover C39 then Q2 mill-event landings and sides.

One mill after each seed. Discover facade walks leftover once, then calls here.
SoT: ``docs/tz_terrain_relief.md`` R41 T-18 / T-20.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from app.application.worldData.generators.terrain.relief.discover.apron import (
    ParentSheers,
    is_q2_seed,
    is_side_seed,
    is_slope_corridor_cell,
    resolve_side_parent,
)
from app.application.worldData.generators.terrain.relief.discover.fronts import FrontStage
from app.application.worldData.generators.terrain.relief.discover.millBuckets import (
    BucketRef,
    MillBuckets,
    Q2_DRAIN_ORDER,
    Q2Kind,
)
from app.application.worldData.generators.terrain.relief.discover.millCorridor import (
    CorridorLive,
    LiveCorridors,
)
from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    EIGHT_DELTAS,
    facing_for_delta,
)
from app.application.worldData.generators.terrain.relief.discover.rim import (
    RimStage,
    seed_rim,
)
from app.application.worldData.generators.terrain.relief.discover.seam import SeamStage
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    FrontGeometry,
    ReliefSurface,
    ReliefVertices,
    cell_z,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind


class MillOrigin(Enum):
    Q1_LEFTOVER = "q1_leftover"
    Q2_LANDING = "q2_landing"
    Q2_SIDE = "q2_side"


@dataclass(frozen=True, slots=True)
class MillPass:
    side_parent: dict[int, int]
    q1_s: float
    q2_s: float


def is_q2_side_event(
    xy: Coord,
    surface: ReliefSurface,
    vertices: ReliefVertices,
    *,
    parent_sheers: ParentSheers,
    live: CorridorLive | None,
) -> bool:
    """Scheduler Q2 side: geometry side, not C39 leftover, not SHEER landing."""
    if seed_rim(xy, surface, vertices):
        return False
    if is_q2_seed(xy, surface, vertices, parent_sheers=parent_sheers):
        return False
    return is_side_seed(xy, surface, vertices, live=live)


def _iter_eight(xy: Coord):
    x, y = xy
    for dx, dy in EIGHT_DELTAS:
        yield (x + dx, y + dy)


def _seed_one(
    *,
    rim: RimStage,
    front: FrontStage,
    seam: SeamStage,
    vertices: ReliefVertices,
    xy: Coord,
    live: LiveCorridors,
    fronts: list[FrontGeometry],
) -> int | None:
    plugin = rim.plugin_for(xy)
    if plugin is None:
        return None
    body = rim.flood(xy, plugin)
    body = {
        cell: z for cell, z in body.items()
        if not is_slope_corridor_cell(cell, vertices, live=live)
    }
    if not body:
        return None
    slot = vertices.add_vertex(body)
    # Occupied landings + known-SHEER first steps are dropped inside propose.
    traces = front.propose(slot, body, plugin)
    fronts.extend(seam.commit(traces, plugin))
    return slot


def run_mill_schedule(
    *,
    rim: RimStage,
    front: FrontStage,
    seam: SeamStage,
    vertices: ReliefVertices,
    surface: ReliefSurface,
    buckets: MillBuckets,
    fronts: list[FrontGeometry],
) -> MillPass:
    """Drain leftover C39 at ``z_top``, then that wave's Q2 landings then sides."""
    live = LiveCorridors(fronts)
    side_parent: dict[int, int] = {}

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

    def _record_side(slot: int, xy: Coord) -> None:
        parent = resolve_side_parent(xy, surface, vertices, live=live)
        if parent is None or parent == slot:
            return
        side_parent[slot] = parent

    def _claim_body(slot: int) -> dict[Coord, int]:
        body = vertices.members[slot - 1]
        for cell, z_cell in body.items():
            buckets.move(BucketRef.claimed(int(z_cell), slot), cell)
        return body

    def _enqueue_q2(
        slot: int,
        z_top: int,
        body: dict[Coord, int],
        new_fronts: Sequence[FrontGeometry],
    ) -> None:
        ref = BucketRef.q2(int(z_top), slot)
        for cell in body:
            for nb in _iter_eight(cell):
                if not is_q2_seed(
                    nb, surface, vertices, parent_sheers=_parent_sheers,
                ):
                    continue
                buckets.move(ref, nb, kind=Q2Kind.LANDING)
        for item in new_fronts:
            for cell in item.corridor:
                for nb in _iter_eight(cell):
                    if buckets.q2_kind(nb) is Q2Kind.LANDING:
                        continue
                    if not is_q2_side_event(
                        nb,
                        surface,
                        vertices,
                        parent_sheers=_parent_sheers,
                        live=live,
                    ):
                        continue
                    buckets.move(ref, nb, kind=Q2Kind.SIDE)

    def _mill(xy: Coord, z_top: int, origin: MillOrigin) -> None:
        n_fronts = len(fronts)
        slot = _seed_one(
            rim=rim,
            front=front,
            seam=seam,
            vertices=vertices,
            xy=xy,
            live=live,
            fronts=fronts,
        )
        if slot is None:
            if origin is not MillOrigin.Q1_LEFTOVER:
                buckets.discard(xy)
            return
        buckets.discard(xy)
        body = _claim_body(slot)
        _enqueue_q2(slot, z_top, body, fronts[n_fronts:])
        if origin is MillOrigin.Q2_SIDE:
            _record_side(slot, xy)

    def _q2_valid(xy: Coord, kind: Q2Kind) -> bool:
        if kind is Q2Kind.LANDING:
            return is_q2_seed(
                xy, surface, vertices, parent_sheers=_parent_sheers,
            )
        if kind is Q2Kind.SIDE:
            return is_q2_side_event(
                xy,
                surface,
                vertices,
                parent_sheers=_parent_sheers,
                live=live,
            )
        raise ValueError(f"unknown Q2 kind: {kind!r}")

    q1_s = 0.0
    q2_s = 0.0
    origin_for_kind = {
        Q2Kind.LANDING: MillOrigin.Q2_LANDING,
        Q2Kind.SIDE: MillOrigin.Q2_SIDE,
    }
    while True:
        z_top = buckets.max_leftover_z()
        if z_top is None:
            break
        t = time.perf_counter()
        for xy in buckets.leftover_z(z_top):
            if not buckets.is_leftover(xy, z_top):
                continue
            if not rim.is_seed(xy):
                continue
            _mill(xy, z_top, MillOrigin.Q1_LEFTOVER)
        q1_s += time.perf_counter() - t
        t = time.perf_counter()
        while True:
            progressed = False
            for kind in Q2_DRAIN_ORDER:
                for xy in buckets.q2_for(z_top, kind):
                    if buckets.q2_kind(xy) is not kind:
                        continue
                    if not _q2_valid(xy, kind):
                        buckets.discard(xy)
                        continue
                    _mill(xy, z_top, origin_for_kind[kind])
                    progressed = True
            if not progressed:
                break
        q2_s += time.perf_counter() - t
        buckets.drop_leftover_z(z_top)
    return MillPass(side_parent=side_parent, q1_s=q1_s, q2_s=q2_s)
