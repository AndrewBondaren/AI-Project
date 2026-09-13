"""Module occupancy primitives — C22 pass 1 and center cluster."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.districtAssembler.planner.parcel import (
    fit_fields,
    rect_fits,
    try_orientations,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    InnerBBox,
    Lattice,
    PackingToken,
    Reservation,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_debug,
)


def span_for(size: int, step: int) -> int:
    return max(1, (size + step - 1) // step)


def module_free(
    occupied: list[list[bool]],
    col: int,
    row: int,
    dc: int,
    dr: int,
) -> bool:
    rows = len(occupied)
    cols = len(occupied[0]) if rows else 0
    if col < 0 or row < 0 or col + dc > cols or row + dr > rows:
        return False
    for r in range(row, row + dr):
        for c in range(col, col + dc):
            if occupied[r][c]:
                return False
    return True


def mark_modules(
    occupied: list[list[bool]],
    col: int,
    row: int,
    dc: int,
    dr: int,
) -> None:
    for r in range(row, row + dr):
        for c in range(col, col + dc):
            occupied[r][c] = True


def place_at(
    lattice: Lattice,
    occupied: list[list[bool]],
    token: PackingToken,
    col: int,
    row: int,
    need_w: int,
    need_h: int,
    rotated: bool,
    pass_id: int,
    cluster_id: str | None = None,
) -> Reservation | None:
    dc = span_for(need_w, lattice.step)
    dr = span_for(need_h, lattice.step)
    if not module_free(occupied, col, row, dc, dr):
        return None
    rect = lattice.module_rect(col, row, dc, dr)
    if not rect_fits(need_w, need_h, rect):
        return None
    mark_modules(occupied, col, row, dc, dr)
    return Reservation(
        token=token,
        col=col,
        row=row,
        span_cols=dc,
        span_rows=dr,
        rect_xy=rect,
        rotated_90=rotated,
        pass_id=pass_id,
        cluster_id=cluster_id,
    )


def center_module(inner: InnerBBox, lattice: Lattice) -> tuple[int, int] | None:
    if lattice.module_count_x() <= 0 or lattice.module_count_y() <= 0:
        return None
    cx = (inner.x0 + inner.x1) // 2
    cy = (inner.y0 + inner.y1) // 2
    col = lattice.module_count_x() - 1
    row = lattice.module_count_y() - 1
    for i in range(lattice.module_count_x()):
        if lattice.xs[i] <= cx < lattice.xs[i + 1]:
            col = i
            break
    for j in range(lattice.module_count_y()):
        if lattice.ys[j] <= cy < lattice.ys[j + 1]:
            row = j
            break
    return col, row


def place_center(
    inner: InnerBBox,
    lattice: Lattice,
    occupied: list[list[bool]],
    token: PackingToken,
    district: str,
    cluster_id: str | None = None,
) -> Reservation | None:
    home = center_module(inner, lattice)
    if home is None:
        return None
    home_c, home_r = home
    for need_w, need_h, rotated in try_orientations(token):
        dc = span_for(need_w, lattice.step)
        dr = span_for(need_h, lattice.step)
        col = max(0, min(home_c - dc // 2, lattice.module_count_x() - dc))
        row = max(0, min(home_r - dr // 2, lattice.module_count_y() - dr))
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
