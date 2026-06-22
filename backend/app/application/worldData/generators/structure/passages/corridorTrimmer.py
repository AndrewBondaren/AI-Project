"""
Post-layout trimming of corridor rooms.
Runs after layout_level (mode_b), before cell generation and wall_openings.
ТЗ: docs/tz_corridor_trim.md
"""
from __future__ import annotations

import logging

from app.application.worldData.generators.structure.roomInstance import _RoomInstance

logger = logging.getLogger(__name__)

_MIN_CORRIDOR_LENGTH = 3


def trim_corridor_rooms(
    all_rooms: list[_RoomInstance],
    template:  dict,
) -> None:
    """
    Shorten each corridor room to the extent of its last attached room.
    Mutates room.depth / room.width / room.origin_y / room.origin_x in-place.
    """
    corridor_to_sc = _build_corridor_to_staircase(template)
    shaft_by_sc    = _build_shaft_by_staircase(all_rooms)
    placed         = [r for r in all_rooms if r.placed]

    for corridor in placed:
        if corridor.room_type != "corridor":
            continue
        sc_id = corridor_to_sc.get(corridor.room_id)
        if sc_id is None:
            continue

        own_shafts = [r for r in shaft_by_sc.get(sc_id, []) if r.z_offset == corridor.z_offset]
        if not own_shafts:
            continue
        shaft = own_shafts[0]

        attached       = [r for r in placed if r.attach_to == corridor.room_id]
        other_fp_cells = _other_shaft_cells(sc_id, corridor.z_offset, shaft_by_sc)

        if corridor.depth >= corridor.width:
            _trim_y(corridor, shaft, attached, other_fp_cells)
        else:
            _trim_x(corridor, shaft, attached, other_fp_cells)


# ---------------------------------------------------------------------------
# Axis-specific trim

def _trim_y(
    corridor:       _RoomInstance,
    shaft:          _RoomInstance,
    attached:       list[_RoomInstance],
    other_fp_cells: set[tuple[int, int]],
) -> None:
    y_min = corridor.origin_y
    y_max = corridor.origin_y + corridor.depth - 1

    shaft_cy = shaft.origin_y + shaft.depth // 2
    if abs(y_min - shaft_cy) <= abs(y_max - shaft_cy):
        start_coord, face_coord = y_min, y_max
    else:
        start_coord, face_coord = y_max, y_min

    step        = -1 if face_coord > start_coord else 1
    x_lo, x_hi = corridor.origin_x, corridor.origin_x + corridor.width - 1
    last_valid  = _walk(face_coord, start_coord, step,
                        attached, "y", other_fp_cells, x_lo, x_hi)

    _apply(corridor, "depth", "origin_y", start_coord, face_coord, last_valid)


def _trim_x(
    corridor:       _RoomInstance,
    shaft:          _RoomInstance,
    attached:       list[_RoomInstance],
    other_fp_cells: set[tuple[int, int]],
) -> None:
    x_min = corridor.origin_x
    x_max = corridor.origin_x + corridor.width - 1

    shaft_cx = shaft.origin_x + shaft.width // 2
    if abs(x_min - shaft_cx) <= abs(x_max - shaft_cx):
        start_coord, face_coord = x_min, x_max
    else:
        start_coord, face_coord = x_max, x_min

    step        = -1 if face_coord > start_coord else 1
    y_lo, y_hi  = corridor.origin_y, corridor.origin_y + corridor.depth - 1
    last_valid  = _walk(face_coord, start_coord, step,
                        attached, "x", other_fp_cells, y_lo, y_hi)

    _apply(corridor, "width", "origin_x", start_coord, face_coord, last_valid)


# ---------------------------------------------------------------------------
# Walk + apply helpers

def _walk(
    face_coord:     int,
    start_coord:    int,
    step:           int,
    attached:       list[_RoomInstance],
    axis:           str,
    other_fp_cells: set[tuple[int, int]],
    perp_lo:        int,
    perp_hi:        int,
) -> int | None:
    """
    Walk from face_coord toward start_coord.
    Return first P (from face side) where an attached room spans P,
    or an other-staircase shaft cell is within 2 cells of corridor walls at P.
    """
    for P in range(face_coord, start_coord + step, step):
        for ar in attached:
            lo = ar.origin_y if axis == "y" else ar.origin_x
            hi = lo + (ar.depth if axis == "y" else ar.width) - 1
            if lo <= P <= hi:
                return P

        for (sx, sy) in other_fp_cells:
            main_val = sy if axis == "y" else sx
            perp_val = sx if axis == "y" else sy
            if abs(main_val - P) <= 1 and (
                abs(perp_val - perp_lo) <= 2 or abs(perp_val - perp_hi) <= 2
            ):
                return P

    return None


def _apply(
    corridor:    _RoomInstance,
    dim_attr:    str,
    origin_attr: str,
    start_coord: int,
    face_coord:  int,
    last_valid:  int | None,
) -> None:
    current_dim = getattr(corridor, dim_attr)
    new_dim     = _MIN_CORRIDOR_LENGTH if last_valid is None else abs(last_valid - start_coord) + 2

    if new_dim >= current_dim:
        return

    logger.info(
        "trim | corridor=%r  %s %d → %d  (last_valid=%s  start=%d  face=%d)",
        corridor.room_id, dim_attr, current_dim, new_dim, last_valid, start_coord, face_coord,
    )
    setattr(corridor, dim_attr, new_dim)
    if face_coord < start_coord:
        setattr(corridor, origin_attr, start_coord - new_dim + 1)


# ---------------------------------------------------------------------------
# Build helpers

def _build_corridor_to_staircase(template: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for sc in template.get("staircases", []):
        sc_id = sc.get("staircase_id", "?")
        for stop in sc.get("stops", [])[1:]:
            result[stop] = sc_id
    return result


def _build_shaft_by_staircase(all_rooms: list[_RoomInstance]) -> dict[str, list[_RoomInstance]]:
    result: dict[str, list[_RoomInstance]] = {}
    for r in all_rooms:
        if r.placed and r.staircase_id:
            result.setdefault(r.staircase_id, []).append(r)
    return result


def _other_shaft_cells(
    own_sc_id:   str,
    z_offset:    int,
    shaft_by_sc: dict[str, list[_RoomInstance]],
) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for sc_id, shafts in shaft_by_sc.items():
        if sc_id == own_sc_id:
            continue
        for shaft in shafts:
            if shaft.z_offset == z_offset and shaft.placed:
                cells |= shaft.get_footprint()
    return cells
