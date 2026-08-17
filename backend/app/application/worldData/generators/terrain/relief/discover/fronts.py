"""R42 lockstep fronts: rim shots, W-runs, W×L walk.

Proposes traces only. Does not mark seam or occ (C41).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    EIGHT_DELTAS,
    GRID_OUTWARD_DELTA,
    facing_for_delta,
    is_cardinal,
    truncate_trace,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    VertexBodyPlugin,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    CapFront,
    CellBlocked,
    Coord,
    ProposedTrace,
    ReliefSurface,
    ReliefVertices,
    cell_z,
)
from app.dataModel.spatial.facing import Facing

_TRACE_CAP = 64


def _diagonal_covered_by_ortho(
    dx: int,
    dy: int,
    x: int,
    y: int,
    z_body: int,
    surface: ReliefSurface,
    body: dict[Coord, int],
) -> bool:
    """NE/NW/SE/SW only if that quadrant has no ortho downhill (R42 / R41)."""
    if dx == 0 or dy == 0:
        return False
    for odx, ody in ((dx, 0), (0, dy)):
        nb = (x + odx, y + ody)
        if nb in body:
            continue
        zn = cell_z(surface, nb)
        if zn is not None and zn < z_body:
            return True
    return False


def _consecutive_runs(
    cells: Sequence[Coord],
    facing: Facing,
) -> list[tuple[Coord, ...]]:
    """Cardinal rim: consecutive along the tangent, same outward face line."""
    if not cells:
        return []
    if not is_cardinal(facing):
        return [((cell,)) for cell in sorted(cells)]
    dx, _dy = GRID_OUTWARD_DELTA[facing]
    if dx != 0:
        by_line: dict[int, list[Coord]] = defaultdict(list)
        for xy in cells:
            by_line[xy[0]].append(xy)
        runs: list[tuple[Coord, ...]] = []
        for x in sorted(by_line):
            col = sorted(by_line[x], key=lambda c: c[1])
            acc = [col[0]]
            for cell in col[1:]:
                if cell[1] == acc[-1][1] + 1:
                    acc.append(cell)
                else:
                    runs.append(tuple(acc))
                    acc = [cell]
            runs.append(tuple(acc))
        return runs
    by_line_y: dict[int, list[Coord]] = defaultdict(list)
    for xy in cells:
        by_line_y[xy[1]].append(xy)
    runs_y: list[tuple[Coord, ...]] = []
    for y in sorted(by_line_y):
        row = sorted(by_line_y[y], key=lambda c: c[0])
        acc = [row[0]]
        for cell in row[1:]:
            if cell[0] == acc[-1][0] + 1:
                acc.append(cell)
            else:
                runs_y.append(tuple(acc))
                acc = [cell]
        runs_y.append(tuple(acc))
    return runs_y


@dataclass(frozen=True, slots=True)
class FrontStage:
    """R42: propose lockstep traces for one vertex. No seam, no occ."""

    surface: ReliefSurface
    vertices: ReliefVertices
    cell_blocked: CellBlocked
    cap_front: CapFront | None = None

    def propose(
        self,
        slot: int,
        body: dict[Coord, int],
        plugin: VertexBodyPlugin,
    ) -> tuple[ProposedTrace, ...]:
        z_body = next(iter(body.values()))
        grouped: dict[tuple[Facing, int], list[Coord]] = defaultdict(list)
        for rim, facing, first_dz in self._rim_shots(body, plugin):
            grouped[(facing, first_dz)].append(rim)

        pending: list[ProposedTrace] = []
        for (facing, first_dz), rims in grouped.items():
            for run in _consecutive_runs(rims, facing):
                if not plugin.allows_unit_stamp() and abs(int(first_dz)) == 1:
                    continue
                trace = self._walk_trace(run, facing, z_body, slot)
                if self.cap_front is not None:
                    max_k = self.cap_front(plugin.context)
                    if max_k is None:
                        continue
                    trace = truncate_trace(trace, run, facing, max_k)
                if not trace:
                    continue
                z_end = cell_z(self.surface, trace[-1])
                if z_end is None:
                    continue
                pending.append(
                    ProposedTrace(
                        slot=slot,
                        z_body=z_body,
                        rim=run,
                        facing=facing,
                        first_dz=first_dz,
                        trace=trace,
                        z_end=z_end,
                    ),
                )
        return tuple(pending)

    def _rim_shots(
        self,
        body: dict[Coord, int],
        plugin: VertexBodyPlugin,
    ) -> list[tuple[Coord, Facing, int]]:
        surface = self.surface
        vertices = self.vertices
        shots: list[tuple[Coord, Facing, int]] = []
        for (x, y), z_body in body.items():
            for dx, dy in EIGHT_DELTAS:
                nb = (x + dx, y + dy)
                if nb in body:
                    continue
                zn = cell_z(surface, nb)
                if zn is None or zn >= z_body:
                    continue
                if _diagonal_covered_by_ortho(dx, dy, x, y, z_body, surface, body):
                    continue
                facing = facing_for_delta((dx, dy))
                if facing is None:
                    continue
                if not plugin.may_shoot((x, y), nb, surface):
                    continue
                ni = vertices.index(nb[0], nb[1])
                if ni is not None and (vertices.occ[ni] != 0 or vertices.seam[ni] != 0):
                    continue
                shots.append(((x, y), facing, z_body - zn))
        return shots

    def _walk_trace(
        self,
        rim: tuple[Coord, ...],
        facing: Facing,
        z_body: int,
        slot: int,
    ) -> tuple[Coord, ...]:
        """Lockstep W×L until θ break, abutment, own body, or foreign occ/seam."""
        dx, dy = GRID_OUTWARD_DELTA[facing]
        surface = self.surface
        vertices = self.vertices
        blocked = self.cell_blocked
        cells: list[Coord] = []
        for k in range(1, _TRACE_CAP + 1):
            strip: list[Coord] = []
            zs: list[int] = []
            for sx, sy in rim:
                xy = (sx + dx * k, sy + dy * k)
                z = cell_z(surface, xy)
                if z is None or blocked(xy):
                    return tuple(cells)
                i = vertices.index(xy[0], xy[1])
                if i is not None:
                    if vertices.at_grid[i] == slot:
                        return tuple(cells)
                    if vertices.occ[i] != 0 or vertices.seam[i] != 0:
                        return tuple(cells)
                if z > z_body:
                    return tuple(cells)
                if k > 1:
                    prev = (sx + dx * (k - 1), sy + dy * (k - 1))
                    zp = cell_z(surface, prev)
                    if zp is None or z > zp:
                        return tuple(cells)
                strip.append(xy)
                zs.append(z)
            if len(set(zs)) > 1:
                return tuple(cells)
            cells.extend(strip)
        return tuple(cells)
