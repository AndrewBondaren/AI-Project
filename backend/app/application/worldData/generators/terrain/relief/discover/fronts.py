"""R42 lockstep fronts: rim shots, W-runs, W×L walk.

One rim cell × one Facing → one ray. (cell, Facing) is unique across
vertices. Proposes traces only. Does not mark seam or occ (C41).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    GRID_OUTWARD_DELTA,
    is_cardinal,
    iter_body_eight_views,
    step_k,
    truncate_trace,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    VertexBodyPlugin,
    shore_condition_at,
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
from app.application.worldData.generators.terrain.relief.sample.terrainMap import (
    map_system_terrain,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTerrainEnvelope import (
    ReliefOntologyEnvelopes,
    ReliefTerrainEnvelope,
)


def _walk_cap(envelope: ReliefTerrainEnvelope, occupancy: int | None) -> int | None:
    """Hard walk bound: min(envelope max, occupancy knobs). None = until natural stop."""
    caps: list[int] = []
    env_max = envelope.slope_walk_cap_cells()
    if env_max is not None:
        caps.append(env_max)
    if occupancy is not None:
        caps.append(int(occupancy))
    if not caps:
        return None
    return max(1, min(caps))


def _diagonal_lands_on_ortho_target(
    dx: int,
    dy: int,
    src: Coord,
    z_body: int,
    surface: ReliefSurface,
    body: dict[Coord, int],
) -> bool:
    """Skip a diagonal if its landing is already an ortho downhill of another rim cell.

    A peak may look all 8 ways: own ortho and diagonal go to different cells.
    A mesa south face must not also fire SE into the neighbor's south landing
    (that would seam the ortho front).
    """
    if dx == 0 or dy == 0:
        return False
    dest = (src[0] + dx, src[1] + dy)
    zn = cell_z(surface, dest)
    if zn is None or zn >= z_body:
        return False
    for odx, ody in ((dx, 0), (0, dy)):
        ortho_src = (dest[0] - odx, dest[1] - ody)
        if ortho_src in body and ortho_src != src:
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
    envelopes: ReliefOntologyEnvelopes | None = None

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
                env = self._envelope_for_run(run, facing)
                if not env.stamps_first_step(abs(int(first_dz)), plugin.context):
                    continue
                occupancy: int | None = None
                if self.cap_front is not None:
                    occupancy = self.cap_front(plugin.context)
                    if occupancy is None:
                        continue
                trace = self._walk_trace(
                    run, facing, z_body, slot, plugin,
                    walk_cap=_walk_cap(env, occupancy),
                    continue_equal_z=self._continue_equal_z(plugin, env),
                )
                if occupancy is not None:
                    trace = truncate_trace(trace, run, facing, occupancy)
                if not trace:
                    continue
                landings = tuple(
                    cell for cell in trace
                    if step_k(cell, run, facing) == 1
                )
                if not self.vertices.claim_facings(landings, facing):
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
        seen: set[tuple[Coord, Facing]] = set()
        for src, facing, nb, z_body, zn in iter_body_eight_views(
            body, lambda xy: cell_z(surface, xy),
        ):
            if nb in body:
                continue
            if zn >= z_body:
                continue
            dx, dy = nb[0] - src[0], nb[1] - src[1]
            if _diagonal_lands_on_ortho_target(
                dx, dy, src, z_body, surface, body,
            ):
                continue
            key = (src, facing)
            if key in seen:
                continue
            if not plugin.may_shoot(src, nb, surface):
                continue
            ni = vertices.index(nb[0], nb[1])
            if ni is not None and vertices.occ[ni] != 0:
                continue
            seen.add(key)
            shots.append((src, facing, z_body - zn))
        return shots

    def _envelope_for_run(
        self,
        run: tuple[Coord, ...],
        facing: Facing,
    ) -> ReliefTerrainEnvelope:
        """Envelope of the first downhill cell (R37 / R41-T-7 / R41-T-11)."""
        dx, dy = GRID_OUTWARD_DELTA[facing]
        sx, sy = run[0]
        downhill = (sx + dx, sy + dy)
        raw = self.surface.terrain_at(downhill) or self.surface.terrain_at((sx, sy))
        mapped = map_system_terrain(raw)
        if mapped is None or not mapped.is_shore_class():
            mapped = (
                shore_condition_at(downhill, self.surface)
                or shore_condition_at((sx, sy), self.surface)
                or mapped
            )
        table = self.envelopes or ReliefOntologyEnvelopes.canonical_defaults()
        return (
            table.for_terrain(mapped)
            if mapped is not None
            else ReliefTerrainEnvelope()
        )

    def _continue_equal_z(
        self,
        plugin: VertexBodyPlugin,
        envelope: ReliefTerrainEnvelope,
    ) -> bool:
        """Ravine / channel bed: flat floor is L. Open-land basin is not."""
        if plugin.context is ReliefContext.RAVINE:
            return True
        return bool(envelope.grades_channel_bed)

    def _walk_trace(
        self,
        rim: tuple[Coord, ...],
        facing: Facing,
        z_body: int,
        slot: int,
        plugin: VertexBodyPlugin,
        *,
        walk_cap: int | None,
        continue_equal_z: bool,
    ) -> tuple[Coord, ...]:
        """Lockstep W×L until θ break, abutment, own body, or foreign occ/seam.

        Rise ``z > z_body`` / ``z > z_prev`` always stops (R41-T-5). Equal z
        continues L only for ravine / channel bed; open-land basin floor is
        not this front's corridor. First-step ``|dz|=1`` is an envelope skip,
        not this predicate. Walk cap is envelope max and/or occupancy knobs
        (R41-T-11). ``None`` = until the heightmap (or equal-z) stop.
        """
        dx, dy = GRID_OUTWARD_DELTA[facing]
        surface = self.surface
        vertices = self.vertices
        blocked = self.cell_blocked
        cells: list[Coord] = []
        k = 0
        while True:
            k += 1
            if walk_cap is not None and k > walk_cap:
                return tuple(cells)
            strip: list[Coord] = []
            zs: list[int] = []
            hit_seam_k1 = False
            for sx, sy in rim:
                xy = (sx + dx * k, sy + dy * k)
                z = cell_z(surface, xy)
                if z is None:
                    return tuple(cells)
                if blocked(xy):
                    role = surface.hydro_role_at(xy)
                    hydro_block = (
                        role is not None and role.blocks_grade_seed()
                    )
                    prev = (sx, sy) if k == 1 else (
                        sx + dx * (k - 1), sy + dy * (k - 1)
                    )
                    if not hydro_block or not plugin.may_shoot(
                        prev, xy, surface,
                    ):
                        return tuple(cells)
                i = vertices.index(xy[0], xy[1])
                if i is not None:
                    if vertices.at_grid[i] == slot:
                        return tuple(cells)
                    if vertices.occ[i] != 0:
                        return tuple(cells)
                    if vertices.seam[i] != 0:
                        if k > 1:
                            return tuple(cells)
                        hit_seam_k1 = True
                if z > z_body:
                    return tuple(cells)
                if k > 1:
                    prev = (sx + dx * (k - 1), sy + dy * (k - 1))
                    zp = cell_z(surface, prev)
                    if zp is None or z > zp:
                        return tuple(cells)
                    if z == zp and not continue_equal_z:
                        return tuple(cells)
                strip.append(xy)
                zs.append(z)
            if len(set(zs)) > 1:
                return tuple(cells)
            cells.extend(strip)
            if hit_seam_k1:
                return tuple(cells)
