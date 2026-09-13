"""CONN-PACK-2 — greedy center cluster around the district home module."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.districtAssembler.planner.occupy import (
    center_module,
    module_free,
    place_at,
    place_center,
    span_for,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.parcel import (
    fit_fields,
    log_place,
    rect_fits,
    try_orientations,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    CenterCluster,
    InnerBBox,
    Lattice,
    PackingToken,
    Rect,
    Reservation,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_debug,
    packing_info,
    packing_warning,
)

_CARDINAL = ((1, 0), (-1, 0), (0, 1), (0, -1))


def cluster_id_for(district: str) -> str:
    return f"{district}:center"


def reservation_modules(reservation: Reservation) -> set[tuple[int, int]]:
    return {
        (col, row)
        for row in range(reservation.row, reservation.row + reservation.span_rows)
        for col in range(reservation.col, reservation.col + reservation.span_cols)
    }


def module_aabb(lattice: Lattice, modules: set[tuple[int, int]]) -> Rect | None:
    if not modules:
        return None
    cols = [col for col, _row in modules]
    rows = [row for _col, row in modules]
    col0, col1 = min(cols), max(cols)
    row0, row1 = min(rows), max(rows)
    return lattice.module_rect(col0, row0, col1 - col0 + 1, row1 - row0 + 1)


def aabb_rects(rects: list[Rect]) -> Rect | None:
    if not rects:
        return None
    return (
        min(rect[0] for rect in rects),
        min(rect[1] for rect in rects),
        max(rect[2] for rect in rects),
        max(rect[3] for rect in rects),
    )


def frame_blocked_rects(reservations: list[Reservation]) -> tuple[Rect, ...]:
    """One hull for the center cluster, plus non-cluster pass-1 rects."""
    cluster = [row for row in reservations if row.cluster_id is not None]
    others = tuple(row.rect_xy for row in reservations if row.cluster_id is None)
    hull = aabb_rects([row.rect_xy for row in cluster])
    if hull is None:
        return others
    return (hull,) + others


def _span_modules(col: int, row: int, dc: int, dr: int) -> set[tuple[int, int]]:
    return {
        (col + dc_i, row + dr_i)
        for dr_i in range(dr)
        for dc_i in range(dc)
    }


def _four_adjacent(
    span: set[tuple[int, int]],
    cluster: set[tuple[int, int]],
) -> bool:
    if span & cluster:
        return False
    for col, row in span:
        for dx, dy in _CARDINAL:
            if (col + dx, row + dy) in cluster:
                return True
    return False


def _min_manhattan(modules: set[tuple[int, int]], home: tuple[int, int]) -> int:
    home_c, home_r = home
    return min(abs(col - home_c) + abs(row - home_r) for col, row in modules)


def _module_aabb_area(modules: set[tuple[int, int]]) -> int:
    cols = [col for col, _row in modules]
    rows = [row for _col, row in modules]
    return (max(cols) - min(cols) + 1) * (max(rows) - min(rows) + 1)


def _seal_hull(
    lattice: Lattice,
    occupied: list[list[bool]],
    modules: set[tuple[int, int]],
) -> Rect | None:
    hull = module_aabb(lattice, modules)
    if hull is None:
        return None
    cols = [col for col, _row in modules]
    rows = [row for _col, row in modules]
    ny = lattice.module_count_y()
    nx = lattice.module_count_x()
    for row in range(min(rows), max(rows) + 1):
        for col in range(min(cols), max(cols) + 1):
            if 0 <= row < ny and 0 <= col < nx:
                occupied[row][col] = True
    return hull


def _log_center_place(district: str, reservation: Reservation) -> None:
    packing_info(
        PackingStep.PASS1, district=district,
        uid=reservation.token.uid, reserved=True,
        span=f"{reservation.span_cols}x{reservation.span_rows}",
        reason=PackingReason.CENTER,
    )
    log_place(district, reservation)


def _log_center_leftover(district: str, token: PackingToken) -> None:
    packing_warning(
        PackingStep.PASS1, district=district,
        uid=token.uid, reserved=False, reason=PackingReason.CENTER,
    )


def _place_adjacent(
    lattice: Lattice,
    occupied: list[list[bool]],
    token: PackingToken,
    district: str,
    cluster_id: str,
    home: tuple[int, int],
    cluster_modules: set[tuple[int, int]],
) -> Reservation | None:
    ny = lattice.module_count_y()
    nx = lattice.module_count_x()
    candidates: list[tuple[tuple[int, int, int, int, int], int, int, int, int, bool]] = []
    for need_w, need_h, rotated in try_orientations(token):
        dc = span_for(need_w, lattice.step)
        dr = span_for(need_h, lattice.step)
        for row in range(ny):
            for col in range(nx):
                if not module_free(occupied, col, row, dc, dr):
                    continue
                rect = lattice.module_rect(col, row, dc, dr)
                if not rect_fits(need_w, need_h, rect):
                    continue
                span = _span_modules(col, row, dc, dr)
                if not _four_adjacent(span, cluster_modules):
                    continue
                key = (
                    _min_manhattan(span, home),
                    1 if rotated else 0,
                    _module_aabb_area(cluster_modules | span),
                    col,
                    row,
                )
                candidates.append((key, col, row, need_w, need_h, rotated))
    candidates.sort(key=lambda item: item[0])
    for _key, col, row, need_w, need_h, rotated in candidates:
        placed = place_at(
            lattice, occupied, token, col, row,
            need_w, need_h, rotated, 1, cluster_id=cluster_id,
        )
        packing_debug(
            PackingStep.FIT, district=district,
            **fit_fields(
                token, "center", rotated,
                "yes" if placed else "no",
                PackingReason.OK if placed else PackingReason.REJECT_AXIS,
            ),
        )
        if placed is not None:
            return placed
    return None


def place_center_cluster(
    inner: InnerBBox,
    lattice: Lattice,
    occupied: list[list[bool]],
    center_tokens: list[PackingToken],
    district: str,
) -> CenterCluster:
    home = center_module(inner, lattice)
    cluster_id = cluster_id_for(district)
    placed: list[Reservation] = []
    leftover: list[PackingToken] = []
    cluster_modules: set[tuple[int, int]] = set()
    for token in center_tokens:
        if not cluster_modules:
            reservation = place_center(
                inner, lattice, occupied, token, district, cluster_id=cluster_id,
            )
        elif home is None:
            reservation = None
        else:
            reservation = _place_adjacent(
                lattice, occupied, token, district, cluster_id, home, cluster_modules,
            )
        if reservation is None:
            leftover.append(token)
            _log_center_leftover(district, token)
            continue
        placed.append(reservation)
        cluster_modules |= reservation_modules(reservation)
        _log_center_place(district, reservation)
    hull = _seal_hull(lattice, occupied, cluster_modules)
    return CenterCluster(
        home=home,
        reservations=tuple(placed),
        hull=hull,
        leftover=tuple(leftover),
    )
