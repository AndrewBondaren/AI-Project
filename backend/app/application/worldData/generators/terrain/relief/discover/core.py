"""Discover orchestrator — leftover walk, mill schedule, sheer traces, C38.

Stages own geometry. Does not write z/uid or fill columns.
SoT: ``docs/tz_terrain_relief.md`` R41.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.discover.fronts import FrontStage
from app.application.worldData.generators.terrain.relief.discover.millBuckets import (
    BucketRef,
    MillBuckets,
)
from app.application.worldData.generators.terrain.relief.discover.millSchedule import (
    run_mill_schedule,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    VertexBodyPlugin,
)
from app.application.worldData.generators.terrain.relief.discover.rim import (
    RimStage,
    iter_rect_z_cells,
    seed_rim,
)
from app.application.worldData.generators.terrain.relief.discover.seam import SeamStage
from app.application.worldData.generators.terrain.relief.discover.timings import (
    GradePipelineTimings,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    CapFront,
    CellBlocked,
    Coord,
    FrontGeometry,
    ReliefSurface,
    ReliefVertices,
)
from app.dataModel.terrain.relief.reliefTerrainEnvelope import ReliefOntologyEnvelopes

__all__ = ["DiscoverResult", "discover_fronts", "reconcile_members", "seed_rim"]


@dataclass(frozen=True, slots=True)
class DiscoverResult:
    """Vertices, committed fronts, bake side-attach, mill CPU-sum."""

    vertices: ReliefVertices
    fronts: tuple[FrontGeometry, ...]
    side_parent: dict[int, int]
    mill: GradePipelineTimings


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
) -> DiscoverResult:
    """One leftover walk; mill schedule; SHEER traces; C41; C38."""
    t0 = time.perf_counter()
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
        setup_s = time.perf_counter() - t0
        return DiscoverResult(
            vertices,
            (),
            {},
            GradePipelineTimings(mill_setup_s=setup_s, mill_s=setup_s),
        )

    rim = RimStage(surface, vertices, plugins)
    front = FrontStage(surface, vertices, cell_blocked, cap_front, envelopes)
    seam = SeamStage(vertices, surface)
    fronts: list[FrontGeometry] = []
    buckets = MillBuckets()
    for xy, z in iter_rect_z_cells(surface, vertices):
        buckets.insert(BucketRef.leftover(z), xy)

    mill_setup_s = time.perf_counter() - t0
    mill_pass = run_mill_schedule(
        rim=rim,
        front=front,
        seam=seam,
        vertices=vertices,
        surface=surface,
        buckets=buckets,
        fronts=fronts,
    )
    t = time.perf_counter()
    for slot, body in enumerate(vertices.members, start=1):
        if not body:
            continue
        plugin = rim.plugin_for(next(iter(body)))
        if plugin is None:
            continue
        traces = front.propose_sheers(slot, body, plugin)
        fronts.extend(seam.commit(traces, plugin))
    mill_sheer_s = time.perf_counter() - t
    t = time.perf_counter()
    fronts = list(seam.finalize(fronts))
    mill_seam_s = time.perf_counter() - t
    t = time.perf_counter()
    reconcile_members(vertices)
    mill_reconcile_s = time.perf_counter() - t
    mill_s = (
        mill_setup_s + mill_pass.q1_s + mill_pass.q2_s
        + mill_sheer_s + mill_seam_s + mill_reconcile_s
    )
    mill = GradePipelineTimings(
        q1_s=mill_pass.q1_s,
        q2_s=mill_pass.q2_s,
        mill_setup_s=mill_setup_s,
        mill_sheer_s=mill_sheer_s,
        mill_seam_s=mill_seam_s,
        mill_reconcile_s=mill_reconcile_s,
        mill_s=mill_s,
    )
    return DiscoverResult(
        vertices,
        tuple(fronts),
        dict(mill_pass.side_parent),
        mill,
    )
