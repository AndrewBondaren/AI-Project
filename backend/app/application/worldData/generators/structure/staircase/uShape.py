"""
U-shape staircase.
ТЗ: docs/tz_staircase_generation.md §6
"""
from __future__ import annotations
import logging
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
from app.application.worldData.generators.structure.facing import Facing
from app.application.worldData.generators.structure.staircase.facingHelper import (
    _V_INIT, _V_TO_FACING,
)

_NS = frozenset({Facing.NORTH, Facing.SOUTH})
_EW = frozenset({Facing.EAST,  Facing.WEST})
from app.application.worldData.generators.structure.staircase.uShapeHelper import (
    flat_positions,
)

logger = logging.getLogger(__name__)
_validator = UShapeValidator()



@dataclass
class UShapeParams:
    facing: str
    ax: int
    ay: int
    width_int: int
    depth_int: int
    march_depth: int       # steps in last march (depth−1)
    march_depth_mid: int   # steps in non-last marches (depth)
    march_count: int
    flat_per_march: int    # stair_floor cells per landing (0 for march_count=1)
    flat_march1: int       # stair_floor cells for single-march path
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
    prev_fr_anchor: tuple[int, int] | None = None,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """
    Returns (fr_anchor, far_anchor, turn_vector).
    If prev_fr_anchor given, picks the opposite near-side corner deterministically.
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

    if prev_fr_anchor is not None:
        # Reuse the same near-wall corner as the previous flight's fr_anchor.
        # In a single-march U-path the last stair always lands at the OPPOSITE corner,
        # so using the same corner avoids placing the anchor on top of that last stair.
        same = [c for c in choices if c[0] == prev_fr_anchor]
        fr, tv = same[0] if same else choices[0]
    else:
        fr, tv = random.choice(choices)

    fx, fy = fr
    far = (2*ax + w-1 - fx, 2*ay + d-1 - fy)
    return fr, far, tv


def _compute_u_params(
    ax: int, ay: int, w: int, d: int, facing: str, z_height: int,
    conn_label: str = "",
    prev_fr_anchor: tuple[int, int] | None = None,
) -> UShapeParams:
    march_depth     = (d - 1) if facing in _NS else (w - 1)
    march_depth_mid = d       if facing in _NS else w

    march_count = max(1, math.ceil((z_height - 1) / march_depth))

    # N path cells
    # _NS: 3-sided path = 2*(d-1) + (w-1) + 1 = w + 2d - 2
    # _EW: 3-sided path = 2*(w-1) + (d-1) + 1 = 2w + d - 2
    N1 = (w + 2 * d - 2) if facing in _NS else (2 * w + d - 2)
    N2 = 2 * w + 2 * d - 4
    total_N = N1 + N2 * (march_count - 1)

    if total_N < z_height:
        raise ValueError(
            f"u_shape {conn_label}: shaft {w}×{d} too small for z_height={z_height} "
            f"(path cells={total_N}, march_count={march_count})"
        )

    flat_march1 = N1 - z_height if march_count == 1 else 0
    if march_count > 1:
        flat_per_march = math.ceil((total_N - z_height) / march_count)
        # z_height должен покрывать оставшиеся после flat клетки пути.
        # Нарушение = геометрически невалидная комбинация z_height + размер шахты.
        if z_height < total_N - flat_per_march * march_count:
            raise ValueError(
                f"u_shape {conn_label}: недостаточно ступеней: "
                f"z_height={z_height} < {total_N - flat_per_march * march_count} "
                f"(total_N={total_N}, flat_per_march={flat_per_march}, march_count={march_count})"
            )
    else:
        flat_per_march = 0

    fr_anchor, far_anchor, turn_vector = _compute_fr_anchor(ax, ay, w, d, facing, prev_fr_anchor)

    return UShapeParams(
        facing=facing,
        ax=ax, ay=ay,
        width_int=w, depth_int=d,
        march_depth=march_depth,
        march_depth_mid=march_depth_mid,
        march_count=march_count,
        flat_per_march=flat_per_march,
        flat_march1=flat_march1,
        turn_vector=turn_vector,
        fr_anchor=fr_anchor,
        far_anchor=far_anchor,
        V_init=_V_INIT[facing],
    )


def _build_u_shape_first(
    params: UShapeParams,
    z_lo: int,
    z_height: int,
    world_uid: str,
    building_uid: str,
    mat: str,
    cells: dict,
    conn_label: str = "",
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """
    Single-march U-path: 3-legged traversal fr_anchor → far wall → to_anchor.
    Leg sizes:
      _NS → leg1=d, leg2=w-1, leg3=d-1  (total = w+2d-2)
      _EW → leg1=w, leg2=d-1, leg3=w-1  (total = 2w+d-2)
    """
    Vx, Vy   = params.V_init
    tvx, tvy = params.turn_vector

    leg1 = params.depth_int       if params.facing in _NS else params.width_int
    leg2 = (params.width_int  - 1) if params.facing in _NS else (params.depth_int - 1)
    leg3 = (params.depth_int  - 1) if params.facing in _NS else (params.width_int - 1)

    # Build ordered path.  Each iteration appends the current cell, then advances.
    # At the turn between legs the cursor is one step past the corner, so we
    # step back along the old direction and apply the new one.
    path_xy: list[tuple[int, int]] = []
    cx, cy = params.fr_anchor

    for _ in range(leg1):
        path_xy.append((cx, cy)); cx += Vx;  cy += Vy
    cx = cx - Vx + tvx;  cy = cy - Vy + tvy        # pivot to turn direction
    for _ in range(leg2):
        path_xy.append((cx, cy)); cx += tvx; cy += tvy
    cx = cx - tvx - Vx;  cy = cy - tvy - Vy         # pivot to -V direction
    for _ in range(leg3):
        path_xy.append((cx, cy)); cx -= Vx;  cy -= Vy

    flat_set = set(flat_positions(
        params.flat_march1,
        params.ax, params.ay, params.width_int, params.depth_int,
        params.facing, params.turn_vector,
        march_index=0,
        conn_label=conn_label,
    ))

    leg1_facing = _V_TO_FACING.get((Vx,   Vy))
    leg2_facing = _V_TO_FACING.get((tvx,  tvy))
    leg3_facing = _V_TO_FACING.get((-Vx, -Vy))

    z = z_lo
    stair_cells: list[tuple[int, int, int]] = []
    floor_cells: list[tuple[int, int, int]] = []

    logger.info(
        "u_shape %s _build_u_shape_first: z_lo=%d z_height=%d flat_march1=%d "
        "fr_anchor=%s facing=%s path_len=%d flat_set=%s",
        conn_label, z_lo, z_height, params.flat_march1,
        params.fr_anchor, params.facing, len(path_xy), flat_set,
    )

    for idx, (px, py) in enumerate(path_xy):
        if idx < leg1:
            cur_facing = leg1_facing
        elif idx < leg1 + leg2:
            cur_facing = leg2_facing
        else:
            cur_facing = leg3_facing

        if (px, py) in flat_set:
            existing = cells.get((px, py, z))
            if existing is None or existing.system_building_element != "staircase":
                cells[(px, py, z)] = _stair_floor_cell(px, py, z, world_uid, building_uid, mat)
            floor_cells.append((px, py, z))
        else:
            cells[(px, py, z)] = _stair_cell(px, py, z, world_uid, building_uid, mat, facing=cur_facing)
            stair_cells.append((px, py, z))
            z += 1

    logger.info(
        "u_shape %s _build_u_shape_first done: %d stair cells, %d floor cells, z_final=%d",
        conn_label, len(stair_cells), len(floor_cells), z,
    )
    return stair_cells, floor_cells


def _build_u_shape(
    params: UShapeParams,
    z_lo: int,
    z_height: int,
    world_uid: str,
    building_uid: str,
    mat: str,
    cells: dict,
    conn_label: str = "",
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """
    Second pass: place staircase and stair_floor cells.
    Returns (stair_cells, floor_cells).
    """
    if params.march_count == 1:
        return _build_u_shape_first(
            params, z_lo, z_height,
            world_uid, building_uid, mat, cells, conn_label,
        )

    anchors = [params.fr_anchor, params.far_anchor]
    Vx, Vy = params.V_init
    z = z_lo
    stair_cells: list[tuple[int, int, int]] = []
    floor_cells: list[tuple[int, int, int]] = []

    logger.info(
        "u_shape %s _build_u_shape: z_lo=%d z_height=%d march_count=%d "
        "march_depth=%d march_depth_mid=%d flat_per_march=%d "
        "fr_anchor=%s far_anchor=%s facing=%s",
        conn_label, z_lo, z_height, params.march_count,
        params.march_depth, params.march_depth_mid, params.flat_per_march,
        params.fr_anchor, params.far_anchor, params.facing,
    )

    for i in range(params.march_count):
        px, py = anchors[i % 2]
        march_facing = _V_TO_FACING.get((Vx, Vy))

        is_last = (i == params.march_count - 1)
        steps = (z_height - i * params.march_depth_mid) if is_last else params.march_depth_mid

        logger.info(
            "u_shape %s march=%d: start=(%d,%d) z=%d steps=%d V=(%d,%d) is_last=%s",
            conn_label, i, px, py, z, steps, Vx, Vy, is_last,
        )

        for _ in range(steps):
            cells[(px, py, z)] = _stair_cell(px, py, z, world_uid, building_uid, mat, facing=march_facing)
            stair_cells.append((px, py, z))
            px += Vx; py += Vy; z += 1

        logger.info(
            "u_shape %s march=%d: placed %d staircase cells, z now=%d",
            conn_label, i, steps, z,
        )

        if not is_last:
            effective_tv = _turn(i, params.turn_vector)
            flat_xys = flat_positions(
                params.flat_per_march,
                params.ax, params.ay, params.width_int, params.depth_int,
                params.facing, effective_tv,
                march_index=i,
                conn_label=conn_label,
            )
            for fx, fy in flat_xys:
                existing = cells.get((fx, fy, z))
                if existing is None or existing.system_building_element != "staircase":
                    cells[(fx, fy, z)] = _stair_floor_cell(
                        fx, fy, z, world_uid, building_uid, mat
                    )
                floor_cells.append((fx, fy, z))

        Vx, Vy = -Vx, -Vy

    logger.info(
        "u_shape %s _build_u_shape done: %d stair cells, %d floor cells, z_final=%d",
        conn_label, len(stair_cells), len(floor_cells), z,
    )
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

        interior_xy = {(x, y) for x, y in interior}
        prev_anchor: tuple[int, int] | None = None
        for (cx, cy, cz), cell in self.cells.items():
            if cz >= self.z_lo:
                continue
            if (cx, cy) not in interior_xy:
                continue
            if cell.system_building_element == "stair_anchor":
                prev_anchor = (cx, cy)
                break
        if prev_anchor is not None:
            logger.info(
                "u_shape %s: detected prev stair_anchor at %s, reusing same corner",
                self.conn_label, prev_anchor,
            )

        params = _compute_u_params(ax, ay, w, d, facing, self.z_height, self.conn_label,
                                   prev_fr_anchor=prev_anchor)

        # Pseudo-column per TZ §0:
        #   march 1:  (w−2)×(d−1) — center block + middle cells of anchor wall
        #   march 2+: (w−2)×(d−2) — center block only
        pseudo: set[tuple[int, int]] = set()
        if w >= 3 and d >= 3:
            # Determine anchor wall row/col (near side = opposite of facing = V_init direction)
            # facing=north → V_init=(0,+1) → near side y=ay; facing=south → y=ay+d-1 etc.
            Vx0, Vy0 = _V_INIT[facing]
            if params.march_count == 1:
                # Center block (not touching any edge)
                pseudo = {
                    (ax + dx, ay + dy)
                    for dx in range(1, w - 1)
                    for dy in range(1, d - 1)
                }
                # Middle cells of anchor wall (excluding corner anchors)
                if Vy0 > 0:   # facing north → anchor wall y=ay
                    anchor_y = ay
                    pseudo |= {(ax + dx, anchor_y) for dx in range(1, w - 1)}
                elif Vy0 < 0: # facing south → anchor wall y=ay+d-1
                    anchor_y = ay + d - 1
                    pseudo |= {(ax + dx, anchor_y) for dx in range(1, w - 1)}
                elif Vx0 > 0: # facing east → anchor wall x=ax
                    anchor_x = ax
                    pseudo |= {(anchor_x, ay + dy) for dy in range(1, d - 1)}
                else:          # facing west → anchor wall x=ax+w-1
                    anchor_x = ax + w - 1
                    pseudo |= {(anchor_x, ay + dy) for dy in range(1, d - 1)}
            else:
                # march 2+: only center block
                pseudo = {
                    (ax + dx, ay + dy)
                    for dx in range(1, w - 1)
                    for dy in range(1, d - 1)
                }

        if params.march_depth < 1:
            raise ValueError(
                f"u_shape {self.conn_label}: march_depth={params.march_depth} < 1 "
                f"(interior {w}×{d}, facing={facing!r})"
            )

        stair_cells, floor_cells = _build_u_shape(
            params, self.z_lo, self.z_height,
            self.world_uid, self.building_uid, self.mat, self.cells,
            conn_label=self.conn_label,
        )

        if not stair_cells:
            raise ValueError(f"u_shape {self.conn_label}: no staircase cells generated")

        # First staircase cell → stair_anchor (inherits facing from march 0 = V_init)
        fx, fy, fz = stair_cells[0]
        self.cells[(fx, fy, fz)] = _stair_anchor_cell(
            fx, fy, fz, self.world_uid, self.building_uid, self.mat,
            facing=facing
        )

        # Fill all non-path interior cells with void.
        # Base floor is handled by the post-step below.
        path_set = {(x, y, z) for x, y, z in stair_cells + floor_cells}
        interior_set = {(x, y) for x, y in interior if (x, y) not in pseudo}

        for z in range(self.z_lo, self.z_top):
            for (x, y) in interior_set:
                if (x, y, z) in path_set:
                    continue
                self.cells[(x, y, z)] = _void_cell(x, y, z, self.world_uid, self.building_uid)

        # Pseudo-column → void on all z
        for (px, py) in pseudo:
            for z in range(self.z_lo, self.z_top + 1):
                self.cells[(px, py, z)] = _void_cell(
                    px, py, z, self.world_uid, self.building_uid,
                )

        # Base floor post-step: first flight only (prev_anchor is None = no to_anchor at z_lo).
        # Fills any void cells at z_lo — including pseudo-column positions — with floor.
        if prev_anchor is None:
            for (x, y) in {(x, y) for x, y in interior}:
                c = self.cells.get((x, y, self.z_lo))
                if c is not None and c.system_building_element == "void":
                    self.cells[(x, y, self.z_lo)] = _floor_cell(
                        x, y, self.z_lo, self.world_uid, self.building_uid, self.mat
                    )

        check_headroom(stair_cells, self.cells, self.conn_label, 2, self.z_lo, self.z_top)

        fr_anchor = (fx, fy)

        lx, ly, _ = stair_cells[-1]

        # exit_v and to_anchor differ between single-march and multi-march.
        if params.march_count == 1:
            # Single-march U-path: last leg runs in -V_init direction.
            # to_anchor = near-wall opposite corner of fr_anchor + one step outside shaft.
            Vx, Vy = -params.V_init[0], -params.V_init[1]
            fr_x, fr_y = params.fr_anchor
            if facing in _NS:
                nw_opp_x = 2 * ax + w - 1 - fr_x
                nw_opp_y = fr_y
            else:
                nw_opp_x = fr_x
                nw_opp_y = 2 * ay + d - 1 - fr_y
            to_anchor_x = nw_opp_x + Vx
            to_anchor_y = nw_opp_y + Vy
        else:
            # Multi-march: exit direction follows parity of last march index.
            last_i = params.march_count - 1
            Vx, Vy = params.V_init
            if last_i % 2 == 1:
                Vx, Vy = -Vx, -Vy
            to_anchor_x, to_anchor_y = lx + Vx, ly + Vy

        # to_anchor: one step from last stair in exit_v direction at z_top.
        # The arch builder places floor at this position before the staircase runs.
        to_anchor_cell = self.cells.get((to_anchor_x, to_anchor_y, self.z_top))
        to_anchor_elem = to_anchor_cell.system_building_element if to_anchor_cell else "пусто"
        if to_anchor_elem != "floor":
            logger.error(
                "u_shape %s: to_anchor (%d,%d,z=%d) должен быть floor, получено %r. "
                "last_stair=(%d,%d,z=%d), exit_v=(%d,%d), facing=%r. "
                "Проверь что арка построена до лестницы и z_height совместим с размером шахты.",
                self.conn_label, to_anchor_x, to_anchor_y, self.z_top,
                to_anchor_elem, lx, ly, self.z_top - 1, Vx, Vy, facing,
            )
        to_anchor = (to_anchor_x, to_anchor_y)

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
