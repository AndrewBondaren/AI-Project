"""Discover orchestrator — C39 then R42 then C41 then C38.

Stages own the geometry. This module only sequences the contract.
Does not write z/uid. Does not fill columns.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.generators.terrain.relief.discover.fronts import FrontStage
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
)
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
    """C39 leftover rims → R42 traces → C41 seam/occ → C38 reconcile."""
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
    for _z, cells in rim.buckets_high_to_low():
        for xy in cells:
            if not rim.is_seed(xy):
                continue
            plugin = rim.plugin_for(xy)
            if plugin is None:
                continue
            body = rim.flood(xy, plugin)
            if not body:
                continue
            slot = vertices.add_vertex(body)
            traces = front.propose(slot, body, plugin)
            fronts.extend(seam.commit(traces, plugin))
    reconcile_members(vertices)
    return vertices, tuple(fronts)
