"""
U-shape staircase.
ТЗ: docs/tz_staircase_generation.md §6
"""
from __future__ import annotations
import logging

from app.application.worldData.generators.structure.cellBuilder import _interior
from app.application.worldData.generators.structure.cellFactory import (
    _stair_cell, _stair_anchor_cell, _stair_floor_cell,
)
from app.application.worldData.generators.structure.staircase.base import (
    StaircaseBuilder, check_headroom,
)
from app.application.worldData.generators.structure.staircase.uShape.uShapeValidator import (
    UShapeValidator,
)
from app.application.worldData.generators.structure.staircase.facingHelper import (
    _V_TO_FACING,
)
from app.application.worldData.generators.structure.staircase.uShape.uShapeHelper import (
    flat_positions,
    _path_intermediates,
    _NS,
    UShapeParams,
    _compute_u_params,
)

logger = logging.getLogger(__name__)
_validator = UShapeValidator()


def _build_u_shape_first_march(
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

    leg1 = params.depth_int        if params.facing in _NS else params.width_int
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

    leg3_facing = _V_TO_FACING.get((-Vx, -Vy))

    z = z_lo
    stair_cells: list[tuple[int, int, int]] = []
    floor_cells: list[tuple[int, int, int]] = []

    logger.info(
        "u_shape %s _build_u_shape_first_march: z_lo=%d z_height=%d flat_march1=%d "
        "fr_anchor=%s facing=%s path_len=%d flat_set=%s",
        conn_label, z_lo, z_height, params.flat_march1,
        params.fr_anchor, params.facing, len(path_xy), flat_set,
    )

    for idx, (px, py) in enumerate(path_xy):
        # Each cell faces toward the NEXT cell in path (linked-list chain).
        # Last cell uses leg3_facing (exit direction toward to_anchor).
        if idx < len(path_xy) - 1:
            nx, ny = path_xy[idx + 1]
            cur_facing = _V_TO_FACING.get((nx - px, ny - py), leg3_facing)
        else:
            cur_facing = leg3_facing

        if (px, py) in flat_set:
            existing = cells.get((px, py, z))
            if existing is None or existing.system_building_element != "staircase":
                cells[(px, py, z)] = _stair_floor_cell(px, py, z, world_uid, building_uid, mat, facing=cur_facing)
            floor_cells.append((px, py, z))
        else:
            cells[(px, py, z)] = _stair_cell(px, py, z, world_uid, building_uid, mat, facing=cur_facing)
            stair_cells.append((px, py, z))
            z += 1

    logger.info(
        "u_shape %s _build_u_shape_first_march done: %d stair cells, %d floor cells, z_final=%d",
        conn_label, len(stair_cells), len(floor_cells), z,
    )
    return stair_cells, floor_cells


def _march_start(
    i: int,
    is_last: bool,
    params: UShapeParams,
    anchors: list[tuple[int, int]],
    V: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Returns (px, py, mvx, mvy) for march i. V = current (Vx, Vy) before any flip."""
    if is_last and i % 2 == 0:
        # Even-indexed last march exits toward near/fr side — start from far_anchor going -V_init.
        px, py = params.far_anchor
        mvx, mvy = -params.V_init[0], -params.V_init[1]
    else:
        # Regular march: anchor determined by parity, direction follows V.
        px, py = anchors[i % 2]
        mvx, mvy = V
    return px, py, mvx, mvy


def _place_march_cells(
    px: int, py: int, z: int,
    steps: int, mvx: int, mvy: int,
    world_uid: str, building_uid: str, mat: str,
    cells: dict,
) -> list[tuple[int, int, int]]:
    """Places staircase cells for one march. Returns list of (x, y, z) placed."""
    march_facing = _V_TO_FACING.get((mvx, mvy))
    placed: list[tuple[int, int, int]] = []
    for _ in range(steps):
        cells[(px, py, z)] = _stair_cell(px, py, z, world_uid, building_uid, mat, facing=march_facing)
        placed.append((px, py, z))
        px += mvx; py += mvy; z += 1
    return placed


def _place_landing(
    i: int,
    end_pos: tuple[int, int],
    next_start: tuple[int, int],
    next_march_dir: tuple[int, int],
    z: int,
    interior_set: set[tuple[int, int]],
    corner_set: set[tuple[int, int]],
    stair_cells: list[tuple[int, int, int]],
    cells: dict,
    world_uid: str,
    building_uid: str,
    mat: str,
    conn_label: str,
    march_facing: str | None,
    march_flat: int = 0,
    ax: int = 0, ay: int = 0, w: int = 0, d: int = 0,
    facing: str = "north",
    turn_vector: tuple[int, int] = (1, 0),
) -> list[tuple[int, int, int]]:
    """
    BFS path from end of march i to start of march i+1.
    Updates facing of last march stair cell. Returns placed stair_floor cells.
    """
    next_i = i + 1
    forbidden_at_z = {(sx, sy) for sx, sy, sz in stair_cells if sz == z - 1 or sz == z - 2}
    intermediates = _path_intermediates(
        end_pos, next_start, interior_set, forbidden_at_z, corner_set, next_march_dir
    )

    if march_flat > 0 and w > 0:
        fp_cells = flat_positions(march_flat, ax, ay, w, d, facing, turn_vector, march_index=i, conn_label=conn_label)
        bfs_xy   = set(intermediates)
        fp_xy    = set(fp_cells)
        logger.info(
            "u_shape %s march=%d->%d: landing BFS=%d flat_target=%d  bfs=%s  fp=%s  match=%s",
            conn_label, i, next_i, len(intermediates), march_flat,
            sorted(bfs_xy), sorted(fp_xy), bfs_xy == fp_xy,
        )
    else:
        logger.info(
            "u_shape %s march=%d->%d: landing path %s->%s via %s",
            conn_label, i, next_i, end_pos, next_start, intermediates,
        )

    chain = intermediates
    first_next_xy = chain[0] if chain else next_start

    # Update facing of last march stair cell (turn toward landing).
    lsx, lsy, lsz = stair_cells[-1]
    turn_dx = first_next_xy[0] - lsx
    turn_dy = first_next_xy[1] - lsy
    if turn_dx != 0: turn_dx //= abs(turn_dx)
    if turn_dy != 0: turn_dy //= abs(turn_dy)
    turn_facing = _V_TO_FACING.get((turn_dx, turn_dy), march_facing)

    if (lsx, lsy) in corner_set and turn_facing == march_facing:
        logger.error(
            "u_shape %s march=%d: последняя ступень (%d,%d,z=%d) в углу шахты, "
            "но turn_facing=%r == march_facing=%r — поворот не произошёл",
            conn_label, i, lsx, lsy, lsz, turn_facing, march_facing,
        )

    existing_last = cells.get((lsx, lsy, lsz))
    if existing_last is not None:
        elem = existing_last.system_building_element
        if elem == "stair_anchor":
            cells[(lsx, lsy, lsz)] = _stair_anchor_cell(
                lsx, lsy, lsz, world_uid, building_uid, mat, facing=turn_facing
            )
        else:
            cells[(lsx, lsy, lsz)] = _stair_cell(
                lsx, lsy, lsz, world_uid, building_uid, mat, facing=turn_facing
            )

    floor_cells: list[tuple[int, int, int]] = []
    for k, (fx, fy) in enumerate(chain):
        if k < len(chain) - 1:
            nfx, nfy = chain[k + 1]
        else:
            nfx, nfy = next_start
        fdx = nfx - fx; fdy = nfy - fy
        if fdx != 0: fdx //= abs(fdx)
        if fdy != 0: fdy //= abs(fdy)
        floor_facing = _V_TO_FACING.get((fdx, fdy))
        existing = cells.get((fx, fy, z))
        if existing is None or existing.system_building_element != "staircase":
            cells[(fx, fy, z)] = _stair_floor_cell(
                fx, fy, z, world_uid, building_uid, mat, facing=floor_facing
            )
        floor_cells.append((fx, fy, z))

    return floor_cells


def _place_l_march(
    i: int,
    anchor: tuple[int, int],
    mvx: int, mvy: int,
    z: int,
    turn_vector: tuple[int, int],
    world_uid: str, building_uid: str, mat: str,
    cells: dict,
    conn_label: str = "",
) -> tuple[list[tuple[int, int, int]], tuple[int, int, int]]:
    """
    L-образный марш для flat=2: 2 staircase + 1 embedded stair_floor на повороте.

    Геометрия:
      inner_start  = anchor + (mvx, mvy)          — первая ступень (угол anchor → stair_floor)
      corner_pos   = inner_start + (mvx, mvy)      — embedded stair_floor (угол шахты)
      step2_pos    = corner_pos + perp             — вторая ступень

    perp = turn_vector для чётных маршей (i%2==0), -turn_vector для нечётных.
    Возвращает (stair_cells=[step1, step2], corner_sf=(x,y,z+1)).
    """
    tvx, tvy = turn_vector
    perp = (tvx, tvy) if i % 2 == 0 else (-tvx, -tvy)
    ppx, ppy = perp

    ix, iy = anchor[0] + mvx, anchor[1] + mvy    # inner_start
    cx, cy = ix + mvx, iy + mvy                   # corner_pos (embedded stair_floor)
    sx2, sy2 = cx + ppx, cy + ppy                 # step2 staircase

    primary_facing = _V_TO_FACING.get((mvx, mvy))
    perp_facing    = _V_TO_FACING.get((ppx, ppy))

    # Шаг 1: staircase на inner_start
    cells[(ix, iy, z)] = _stair_cell(ix, iy, z, world_uid, building_uid, mat, facing=primary_facing)
    # Embedded stair_floor на углу (z+1 — следующий уровень посадки)
    cells[(cx, cy, z + 1)] = _stair_floor_cell(cx, cy, z + 1, world_uid, building_uid, mat, facing=perp_facing)
    # Шаг 2: staircase за углом
    cells[(sx2, sy2, z + 1)] = _stair_cell(sx2, sy2, z + 1, world_uid, building_uid, mat, facing=perp_facing)

    logger.info(
        "u_shape %s march=%d L-march: anchor=%s inner=(%d,%d,z=%d) corner_sf=(%d,%d,z=%d) step2=(%d,%d,z=%d) perp=%s",
        conn_label, i, anchor, ix, iy, z, cx, cy, z + 1, sx2, sy2, z + 1, perp_facing,
    )

    stair_cells = [(ix, iy, z), (sx2, sy2, z + 1)]
    corner_sf   = (cx, cy, z + 1)
    return stair_cells, corner_sf


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
        return _build_u_shape_first_march(
            params, z_lo, z_height,
            world_uid, building_uid, mat, cells, conn_label,
        )

    anchors = [params.fr_anchor, params.far_anchor]
    Vx, Vy = params.V_init
    z = z_lo
    stair_cells: list[tuple[int, int, int]] = []
    floor_cells: list[tuple[int, int, int]] = []

    interior_set = {
        (params.ax + dx, params.ay + dy)
        for dx in range(params.width_int)
        for dy in range(params.depth_int)
        if dx == 0 or dx == params.width_int - 1 or dy == 0 or dy == params.depth_int - 1
    }
    corner_set = {
        (params.ax + dx, params.ay + dy)
        for dx in range(params.width_int)
        for dy in range(params.depth_int)
        if (dx == 0 or dx == params.width_int - 1) and (dy == 0 or dy == params.depth_int - 1)
    }

    logger.info(
        "u_shape %s _build_u_shape: z_lo=%d z_height=%d march_count=%d "
        "march_depth=%d march_depth_mid=%d "
        "fr_anchor=%s far_anchor=%s facing=%s",
        conn_label, z_lo, z_height, params.march_count,
        params.march_depth, params.march_depth_mid,
        params.fr_anchor, params.far_anchor, params.facing,
    )

    for i in range(params.march_count):
        is_last = (i == params.march_count - 1)
        flat    = params.march_flat[i]
        use_l   = not is_last and flat == 2 and params.width_int >= 3
        px, py, mvx, mvy = _march_start(i, is_last, params, anchors, (Vx, Vy))
        steps = params.march_steps[i]

        logger.info(
            "u_shape %s march=%d: start=(%d,%d) z=%d steps=%d flat_target=%d V=(%d,%d) is_last=%s use_l=%s",
            conn_label, i, px, py, z, steps, flat, mvx, mvy, is_last, use_l,
        )

        if use_l:
            anchor = (px, py)
            march_cells, corner_sf = _place_l_march(
                i, anchor, mvx, mvy, z,
                params.turn_vector,
                world_uid, building_uid, mat, cells, conn_label,
            )
            stair_cells.extend(march_cells)
            floor_cells.append(corner_sf)
            z += 2  # всегда 2 staircase-ступени у L-марша
        else:
            march_cells = _place_march_cells(px, py, z, steps, mvx, mvy, world_uid, building_uid, mat, cells)
            stair_cells.extend(march_cells)
            z += steps

        logger.info(
            "u_shape %s march=%d: placed %d staircase cells, z now=%d",
            conn_label, i, len(march_cells), z,
        )

        if not is_last:
            next_i       = i + 1
            next_is_last = (next_i == params.march_count - 1)
            next_flat    = params.march_flat[next_i]
            next_use_l   = not next_is_last and next_flat == 2 and params.width_int >= 3

            next_px, next_py, next_mvx, next_mvy = _march_start(
                next_i, next_is_last, params, anchors, (-Vx, -Vy)
            )
            # Если следующий марш L-образный, лендинг ведём к inner_start (anchor+step),
            # а не к самому anchor: это освобождает угол-anchor в stair_floor.
            if next_use_l:
                land_target_x = next_px + next_mvx
                land_target_y = next_py + next_mvy
            else:
                land_target_x, land_target_y = next_px, next_py

            end_pos = (march_cells[-1][0], march_cells[-1][1])
            new_floor = _place_landing(
                i, end_pos, (land_target_x, land_target_y), (next_mvx, next_mvy),
                z, interior_set, corner_set, stair_cells, cells,
                world_uid, building_uid, mat, conn_label, _V_TO_FACING.get((mvx, mvy)),
                march_flat=flat,
                ax=params.ax, ay=params.ay, w=params.width_int, d=params.depth_int,
                facing=params.facing, turn_vector=params.turn_vector,
            )
            floor_cells.extend(new_floor)

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

        self.path_set = {(x, y, z) for x, y, z in stair_cells + floor_cells}
        self._is_first_flight = (prev_anchor is None)

        # First staircase cell → stair_anchor (inherits facing from march 0 = V_init)
        fx, fy, fz = stair_cells[0]
        self.cells[(fx, fy, fz)] = _stair_anchor_cell(
            fx, fy, fz, self.world_uid, self.building_uid, self.mat,
            facing=facing
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
            # Multi-march: exit direction = направление последнего марша.
            # Берём из последних двух stair_cells — корректно при любом enforcement.
            prev_lx, prev_ly, _ = stair_cells[-2]
            Vx, Vy = lx - prev_lx, ly - prev_ly
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
            stair_cells=stair_cells,
            turn_vector=params.turn_vector,
        )

        return fr_anchor, to_anchor
