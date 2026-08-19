"""C41 ray-seam: all traces, then seam, then unique corridors / occ.

Does not seed rims or walk new traces.

Uniqueness: one rim cell × one Facing → one ray. A (cell, Facing) landing
is unique across vertices. Several vertices may shoot into a depression
with different Facings; a second ray with the same Facing into the same
cell is rejected at claim. A cell in ≥2 traces of the same Facing is
parallel fur (seam). A cell in traces of different Facings — including
across vertices after finalize — is a shared bottom (seam, not occ).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    cell_at_max_outward_k,
    is_local_min,
    max_outward_k,
    step_k,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    VertexBodyPlugin,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    FOREIGN_MARK,
    Coord,
    FrontGeometry,
    ProposedTrace,
    ReliefSurface,
    ReliefVertices,
    cell_z,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefContext


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


def _geometry(
    item: ProposedTrace,
    *,
    context: ReliefContext,
    corridor: tuple[Coord, ...],
    hit_seam: bool,
    seam_xy: Coord | None,
    surface: ReliefSurface,
) -> FrontGeometry | None:
    if not corridor:
        return None
    bottom = seam_xy if hit_seam and seam_xy is not None else corridor[-1]
    end_cell = cell_at_max_outward_k(corridor, item.rim, item.facing)
    z_end = cell_z(surface, end_cell) if end_cell is not None else None
    path_length = max_outward_k(corridor, item.rim, item.facing)
    if z_end is None or path_length < 1:
        return None
    return FrontGeometry(
        slot=item.slot,
        context=context,
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
    )


@dataclass(frozen=True, slots=True)
class SeamStage:
    """C41: commit proposed traces — seam first, then occ. Finalize after cascade."""

    vertices: ReliefVertices
    surface: ReliefSurface

    def commit(
        self,
        traces: Sequence[ProposedTrace],
        plugin: VertexBodyPlugin,
    ) -> tuple[FrontGeometry, ...]:
        if not traces:
            return ()
        by_facing: dict[Facing, Counter[Coord]] = defaultdict(Counter)
        facings_for_cell: dict[Coord, set[Facing]] = defaultdict(set)
        for item in traces:
            by_facing[item.facing].update(item.trace)
            for cell in item.trace:
                facings_for_cell[cell].add(item.facing)
        same_facing_seam = {
            cell
            for counts in by_facing.values()
            for cell, n in counts.items()
            if n >= 2
        }
        shared_anchor = {
            cell for cell, faces in facings_for_cell.items() if len(faces) >= 2
        }
        seam_cells = same_facing_seam | shared_anchor
        slot = traces[0].slot
        for cell in seam_cells:
            self.vertices.mark_seam(cell, slot)

        fronts: list[FrontGeometry] = []
        for item in traces:
            corridor, hit_seam, seam_xy = _prefix_until_seam(
                item.trace, item.rim, item.facing, seam_cells,
            )
            geom = _geometry(
                item,
                context=plugin.context,
                corridor=corridor,
                hit_seam=hit_seam,
                seam_xy=seam_xy,
                surface=self.surface,
            )
            if geom is None:
                continue
            fronts.append(geom)
            for cell in corridor:
                if is_local_min(self.surface, cell):
                    continue
                self.vertices.mark_occ(cell, item.slot)
        return tuple(fronts)

    def finalize(
        self,
        fronts: Sequence[FrontGeometry],
    ) -> tuple[FrontGeometry, ...]:
        """Cross-vertex C41: shared pit / duplicate landing is seam, not occ."""
        if not fronts:
            return ()
        verts = self.vertices
        counts: Counter[Coord] = Counter()
        for front in fronts:
            counts.update(front.corridor)
        shared = {cell for cell, n in counts.items() if n >= 2}
        for ly in range(verts.height):
            for lx in range(verts.width):
                i = ly * verts.width + lx
                bits = verts.facing_bits[i]
                if bits != 0 and (bits & (bits - 1)) != 0:
                    shared.add((verts.origin_x + lx, verts.origin_y + ly))
        for cell in shared:
            i = verts.index(cell[0], cell[1])
            if i is None:
                continue
            if verts.seam[i] == 0:
                verts.mark_seam(cell, FOREIGN_MARK)
            verts.occ[i] = 0

        out: list[FrontGeometry] = []
        for front in fronts:
            corridor = tuple(
                cell for cell in front.corridor
                if (i := verts.index(cell[0], cell[1])) is None or verts.seam[i] == 0
            )
            if not corridor:
                continue
            end_cell = cell_at_max_outward_k(corridor, front.rim, front.outward)
            z_end = cell_z(self.surface, end_cell) if end_cell is not None else None
            path_length = max_outward_k(corridor, front.rim, front.outward)
            if z_end is None or path_length < 1:
                continue
            hit = front.hit_seam or bool(shared.intersection(front.corridor))
            bottom = corridor[-1]
            if hit:
                seamed = shared.intersection(front.trace)
                if seamed:
                    bottom = next(iter(seamed))
            out.append(
                replace(
                    front,
                    corridor=corridor,
                    z_end=z_end,
                    path_length=path_length,
                    hit_seam=hit,
                    anchor_bottom=bottom,
                ),
            )
            for cell in corridor:
                i = verts.index(cell[0], cell[1])
                if i is not None and verts.occ[i] == 0 and verts.seam[i] == 0:
                    verts.mark_occ(cell, front.slot)
        return tuple(out)
