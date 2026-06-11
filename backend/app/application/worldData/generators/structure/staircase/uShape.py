"""
U-shape staircase.
ТЗ: docs/tz_staircase_generation.md §6
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass

from app.application.worldData.generators.structure.cellBuilder import _interior
from app.application.worldData.generators.structure.cellFactory import (
    _stair_cell, _stair_anchor_cell, _stair_floor_cell, _floor_cell, _void_cell,
)
from app.application.worldData.generators.structure.staircase.base import (
    StaircaseBuilder, check_headroom,
)
from app.application.worldData.generators.structure.staircase.validator import (
    UShapeValidator,
)

_validator = UShapeValidator()


# Initial march direction per TZ facing (facing = far end direction)
_V_INIT: dict[str, tuple[int, int]] = {
    "north": (0, +1),
    "south": (0, -1),
    "east":  (+1,  0),
    "west":  (-1,  0),
}


@dataclass
class UShapeParams:
    facing: str
    ax: int
    ay: int
    width_int: int
    depth_int: int
    march_depth: int
    march_count: int
    loops: int
    path_2d_len: int
    total_stair_floor: int
    landing_width: int
    turn_vector: tuple[int, int]
    fr_anchor: tuple[int, int]
    far_anchor: tuple[int, int]
    V_init: tuple[int, int]


def _turn(march_index: int, turn_vector: tuple[int, int]) -> tuple[int, int]:
    """Shared turn method. Even marches end at far side → +tv; odd → −tv."""
    if march_index % 2 == 0:
        return turn_vector
    return (-turn_vector[0], -turn_vector[1])


def _compute_fr_anchor(
    ax: int, ay: int, w: int, d: int, facing: str,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """
    Random fr_anchor from two valid near-side corners.
    Returns (fr_anchor, far_anchor, turn_vector).
    far_anchor = diagonally opposite corner in interior.
    """
    if facing == "north":
        choices = [((ax,       ay), (+1, 0)),
                   ((ax+w-1,   ay), (-1, 0))]
    elif facing == "south":
        choices = [((ax,       ay+d-1), (+1, 0)),
                   ((ax+w-1,   ay+d-1), (-1, 0))]
    elif facing == "east":
        choices = [((ax, ay),       (0, +1)),
                   ((ax, ay+d-1),   (0, -1))]
    else:  # west
        choices = [((ax+w-1, ay),     (0, +1)),
                   ((ax+w-1, ay+d-1), (0, -1))]

    fr, tv = random.choice(choices)
    fx, fy = fr
    far = (2*ax + w-1 - fx, 2*ay + d-1 - fy)
    return fr, far, tv


def _compute_u_params(
    ax: int, ay: int, w: int, d: int, facing: str, z_height: int,
) -> UShapeParams:
    is_ns = facing in ("north", "south")
    march_depth = (d - 1) if is_ns else (w - 1)
    march_count = math.ceil(z_height / march_depth)
    loops = math.ceil(march_count / 2)

    wall_len = (w - 1) if is_ns else (d - 1)  # landing cells per side

    if march_count <= 1:
        path_2d_len = march_depth
    elif march_count == 2:
        path_2d_len = 2 * march_depth + wall_len
    else:
        path_2d_len = 2 * march_depth + 2 * wall_len

    total_stair_floor = path_2d_len * loops - z_height
    landing_width = math.ceil(total_stair_floor / march_count) if march_count > 1 else 0

    fr_anchor, far_anchor, turn_vector = _compute_fr_anchor(ax, ay, w, d, facing)

    return UShapeParams(
        facing=facing,
        ax=ax, ay=ay,
        width_int=w, depth_int=d,
        march_depth=march_depth,
        march_count=march_count,
        loops=loops,
        path_2d_len=path_2d_len,
        total_stair_floor=total_stair_floor,
        landing_width=landing_width,
        turn_vector=turn_vector,
        fr_anchor=fr_anchor,
        far_anchor=far_anchor,
        V_init=_V_INIT[facing],
    )


def _build_u_shape(
    params: UShapeParams,
    z_lo: int,
    z_height: int,
    world_uid: str,
    building_uid: str,
    mat: str,
    cells: dict,
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """
    Second pass: place staircase and stair_floor cells.
    Returns (stair_cells, floor_cells).
    """
    anchors = [params.fr_anchor, params.far_anchor]
    Vx, Vy = params.V_init
    z = z_lo
    stair_cells: list[tuple[int, int, int]] = []
    floor_cells: list[tuple[int, int, int]] = []

    q_s, r_s = divmod(z_height, params.march_count)

    n_land = params.march_count - 1
    if n_land > 0 and params.total_stair_floor > 0:
        q_l, r_l = divmod(params.total_stair_floor, n_land)
    else:
        q_l, r_l = 0, 0

    _V_TO_FACING = {(0,1):"north",(0,-1):"south",(1,0):"east",(-1,0):"west"}

    for i in range(params.march_count):
        px, py = anchors[i % 2]
        march_facing = _V_TO_FACING.get((Vx, Vy))

        steps = (q_s + 1) if i < r_s else q_s
        for _ in range(steps):
            cells[(px, py, z)] = _stair_cell(px, py, z, world_uid, building_uid, mat, facing=march_facing)
            stair_cells.append((px, py, z))
            px += Vx; py += Vy; z += 1

        # Landing — not for last march
        if i < params.march_count - 1:
            tvx, tvy = _turn(i, params.turn_vector)
            landing_count = (q_l + 1) if i < r_l else q_l
            for _ in range(landing_count):
                existing = cells.get((px, py, z))
                if existing is None or existing.system_building_element != "staircase":
                    cells[(px, py, z)] = _stair_floor_cell(
                        px, py, z, world_uid, building_uid, mat
                    )
                floor_cells.append((px, py, z))
                px += tvx; py += tvy

        Vx, Vy = -Vx, -Vy

    return stair_cells, floor_cells


class UShapeBuilder(StaircaseBuilder):

    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        if self.shaft is not None:
            # New schema: interior = shaft footprint interior; facing from shaft
            interior = list(_interior(self.shaft.get_footprint()))
            facing = self.shaft.facing or "north"
        else:
            # Old schema: interior = overlap of fr and to footprints
            fr_int = _interior(self.fr.get_footprint())
            to_int = _interior(self.to.get_footprint())
            interior = list(fr_int & to_int) or list(to_int)
            facing = self.to.facing or "north"

        xs = sorted(x for x, _ in interior)
        ys = sorted(y for _, y in interior)
        ax, ay = min(xs), min(ys)
        w = max(xs) - ax + 1
        d = max(ys) - ay + 1

        if w < 2 or d < 2:
            raise ValueError(
                f"u_shape {self.conn_label}: interior {w}×{d} too small"
            )

        # Pseudo-column: center (N−2)×(N−2) void block for square rooms
        pseudo: set[tuple[int, int]] = set()
        if w == d and w >= 3:
            pseudo = {
                (ax + dx, ay + dy)
                for dx in range(1, w - 1)
                for dy in range(1, d - 1)
            }

        params = _compute_u_params(ax, ay, w, d, facing, self.z_height)

        if params.march_depth < 1:
            raise ValueError(
                f"u_shape {self.conn_label}: march_depth={params.march_depth} < 1 "
                f"(interior {w}×{d}, facing={facing!r})"
            )

        stair_cells, floor_cells = _build_u_shape(
            params, self.z_lo, self.z_height,
            self.world_uid, self.building_uid, self.mat, self.cells,
        )

        if not stair_cells:
            raise ValueError(f"u_shape {self.conn_label}: no staircase cells generated")

        # First staircase cell → stair_anchor (inherits facing from march 0 = V_init)
        fx, fy, fz = stair_cells[0]
        self.cells[(fx, fy, fz)] = _stair_anchor_cell(
            fx, fy, fz, self.world_uid, self.building_uid, self.mat,
            facing=facing
        )

        # Fill non-path interior: floor at z_lo (base), void above (shaft), z_top untouched
        path_set = {(x, y, z) for x, y, z in stair_cells + floor_cells}
        interior_set = {(x, y) for x, y in interior if (x, y) not in pseudo}

        for z in range(self.z_lo, self.z_top):
            for (x, y) in interior_set:
                if (x, y, z) in path_set:
                    continue
                if z == self.z_lo:
                    self.cells[(x, y, z)] = _floor_cell(
                        x, y, z, self.world_uid, self.building_uid, self.mat
                    )
                else:
                    self.cells[(x, y, z)] = _void_cell(
                        x, y, z, self.world_uid, self.building_uid,
                    )

        # Pseudo-column → void on all z
        for (px, py) in pseudo:
            for z in range(self.z_lo, self.z_top + 1):
                self.cells[(px, py, z)] = _void_cell(
                    px, py, z, self.world_uid, self.building_uid,
                )

        check_headroom(stair_cells, self.cells, self.conn_label, 2, self.z_lo, self.z_top)

        fr_anchor = (fx, fy)

        # to_anchor: nearest floor cell adjacent to footprint at z_top.
        # Prefer exit direction (last march), fall back to all 4 sides.
        last_i = params.march_count - 1
        Vx, Vy = params.V_init
        if last_i % 2 == 1:
            Vx, Vy = -Vx, -Vy

        # New schema: search for to_anchor just outside shaft entry-side (= cells in to_room).
        # Old schema: search just outside to_room footprint (= staircase_room adjacents).
        footprint_to = (self.shaft.get_footprint() if self.shaft is not None
                        else self.to.get_footprint())
        lx, ly, _ = stair_cells[-1]

        def _edge_candidates(dx: int, dy: int) -> list[tuple[int, int]]:
            if dx != 0:
                edge_x = max(x for x, _ in footprint_to) if dx > 0 else min(x for x, _ in footprint_to)
                return [(edge_x + dx, y) for x, y in footprint_to
                        if x == edge_x and (edge_x + dx, y) not in footprint_to]
            else:
                edge_y = max(y for _, y in footprint_to) if dy > 0 else min(y for _, y in footprint_to)
                return [(x, edge_y + dy) for x, y in footprint_to
                        if y == edge_y and (x, edge_y + dy) not in footprint_to]

        # Build candidate list: exit direction first, then remaining 3 sides
        all_dirs = [(Vx, Vy), (0, 1), (0, -1), (1, 0), (-1, 0)]
        seen: set[tuple[int, int]] = set()
        candidates: list[tuple[int, int]] = []
        for dx, dy in all_dirs:
            for pt in _edge_candidates(dx, dy):
                if pt not in seen:
                    seen.add(pt)
                    candidates.append(pt)

        candidates.sort(key=lambda p: abs(p[0] - lx) + abs(p[1] - ly))

        # Prefer natural arrival: cell where player steps off the last stair
        arrival_x, arrival_y = lx + Vx, ly + Vy
        arrival_cell = self.cells.get((arrival_x, arrival_y, self.z_top))
        if arrival_cell is not None and arrival_cell.system_building_element == "floor":
            to_anchor = (arrival_x, arrival_y)
        else:
            to_anchor = None
            for ox, oy in candidates:
                nb = self.cells.get((ox, oy, self.z_top))
                if nb is not None and nb.system_building_element == "floor":
                    to_anchor = (ox, oy)
                    break

        if to_anchor is None:
            debug_cells = {p: self.cells.get((p[0], p[1], self.z_top)) for p in candidates[:5]}
            debug_types = {p: (c.system_building_element if c else "пусто") for p, c in debug_cells.items()}
            raise ValueError(
                f"u_shape {self.conn_label}: нет floor для to_anchor — "
                f"z={self.z_top}, facing={facing!r}, exit_V=({Vx},{Vy}); "
                f"last_cell=({lx},{ly}); arrival=({arrival_x},{arrival_y}); "
                f"candidates_checked={debug_types!r}"
            )

        _shaft_fp = set(self.shaft.get_footprint()) if self.shaft is not None else set()
        _shaft_int = set(_interior(self.shaft.get_footprint())) if self.shaft is not None else set()
        _validator.validate(
            fr_anchor=fr_anchor,
            to_anchor=to_anchor,
            last_stair=(lx, ly),
            exit_v=(Vx, Vy),
            z_lo=self.z_lo, z_top=self.z_top,
            cells=self.cells,
            conn_label=self.conn_label,
            shaft_footprint=_shaft_fp,
            shaft_interior=_shaft_int,
            facing=facing,
        )

        return fr_anchor, to_anchor
