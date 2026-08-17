"""C41 ray-seam: all traces, then seam, then unique corridors / occ.

Does not seed rims or walk new traces.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    cell_at_max_outward_k,
    max_outward_k,
    step_k,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    VertexBodyPlugin,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    FrontGeometry,
    ProposedTrace,
    ReliefSurface,
    ReliefVertices,
    cell_z,
)
from app.dataModel.spatial.facing import Facing


def _column_cells(
    trace: tuple[Coord, ...],
    rim_cell: Coord,
    facing: Facing,
) -> tuple[Coord, ...]:
    owned = []
    for cell in trace:
        k = step_k(cell, (rim_cell,), facing)
        if k is None:
            continue
        owned.append((k, cell))
    owned.sort(key=lambda item: item[0])
    return tuple(cell for _k, cell in owned)


def _prefix_until_seam(
    trace: tuple[Coord, ...],
    rim: tuple[Coord, ...],
    facing: Facing,
    seam: set[Coord],
) -> tuple[tuple[Coord, ...], bool, Coord | None]:
    """Per-column prefix before seam. A W-hole does not split the front (C41)."""
    out: list[Coord] = []
    seen: set[Coord] = set()
    hit = False
    first_seam: Coord | None = None
    for rim_cell in rim:
        for cell in _column_cells(trace, rim_cell, facing):
            if cell in seam:
                hit = True
                if first_seam is None:
                    first_seam = cell
                break
            if cell not in seen:
                seen.add(cell)
                out.append(cell)
    bottom = first_seam if hit and first_seam is not None else (out[-1] if out else None)
    return tuple(out), hit, bottom


@dataclass(frozen=True, slots=True)
class SeamStage:
    """C41: commit proposed traces — seam first, then occ."""

    vertices: ReliefVertices
    surface: ReliefSurface

    def commit(
        self,
        traces: Sequence[ProposedTrace],
        plugin: VertexBodyPlugin,
    ) -> tuple[FrontGeometry, ...]:
        if not traces:
            return ()
        counts: Counter[Coord] = Counter()
        for item in traces:
            counts.update(item.trace)
        seam_cells = {cell for cell, n in counts.items() if n >= 2}
        slot = traces[0].slot
        for cell in seam_cells:
            self.vertices.mark_seam(cell, slot)

        fronts: list[FrontGeometry] = []
        for item in traces:
            corridor, hit_seam, seam_xy = _prefix_until_seam(
                item.trace, item.rim, item.facing, seam_cells,
            )
            if not corridor:
                continue
            bottom = seam_xy if hit_seam and seam_xy is not None else corridor[-1]
            end_cell = cell_at_max_outward_k(corridor, item.rim, item.facing)
            z_end = cell_z(self.surface, end_cell) if end_cell is not None else None
            path_length = max_outward_k(corridor, item.rim, item.facing)
            if z_end is None or path_length < 1:
                continue
            fronts.append(
                FrontGeometry(
                    slot=item.slot,
                    context=plugin.context,
                    outward=item.facing,
                    first_dz=item.first_dz,
                    z_body=item.z_body,
                    z_end=z_end,
                    path_length=path_length,
                    rim=item.rim,
                    trace=item.trace,
                    corridor=corridor,
                    anchor_bottom=bottom,
                    hit_seam=hit_seam,
                ),
            )
            for cell in corridor:
                self.vertices.mark_occ(cell, item.slot)
        return tuple(fronts)
