"""C22 pass 1 — priority reservations on the district lattice."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.corridor import (
    module_blocked_by_corridor,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.parcel import (
    fit_fields,
    log_place,
    rect_fits,
    try_orientations,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
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
from app.dataModel.settlement.district.requiredStructure import POSITION_CENTER


def _span_for(size: int, step: int) -> int:
    return max(1, (size + step - 1) // step)


def _pass1_order(tokens: list[PackingToken]) -> list[PackingToken]:
    required = [t for t in tokens if t.required]
    rest = [t for t in tokens if (not t.required) and t.priority > 0]
    rest.sort(key=lambda t: (-t.priority, -max(t.w, t.h), -min(t.w, t.h), t.uid))
    return required + rest


def _module_free(
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


def _mark(
    occupied: list[list[bool]],
    col: int,
    row: int,
    dc: int,
    dr: int,
) -> None:
    for r in range(row, row + dr):
        for c in range(col, col + dc):
            occupied[r][c] = True


def _init_occupied(
    slot: DistrictSlot,
    lattice: Lattice,
    corridor_rects: tuple[Rect, ...],
) -> list[list[bool]]:
    ny = lattice.module_count_y()
    nx = lattice.module_count_x()
    occupied = [[False] * nx for _ in range(ny)]
    for row in range(ny):
        for col in range(nx):
            if module_blocked_by_corridor(
                lattice, col, row, corridor_rects, slot.entry_nodes,
            ):
                occupied[row][col] = True
    return occupied


def _place_at(
    lattice: Lattice,
    occupied: list[list[bool]],
    token: PackingToken,
    col: int,
    row: int,
    need_w: int,
    need_h: int,
    rotated: bool,
    pass_id: int,
) -> Reservation | None:
    dc = _span_for(need_w, lattice.step)
    dr = _span_for(need_h, lattice.step)
    if not _module_free(occupied, col, row, dc, dr):
        return None
    rect = lattice.module_rect(col, row, dc, dr)
    if not rect_fits(need_w, need_h, rect):
        return None
    _mark(occupied, col, row, dc, dr)
    return Reservation(
        token=token,
        col=col,
        row=row,
        span_cols=dc,
        span_rows=dr,
        rect_xy=rect,
        rotated_90=rotated,
        pass_id=pass_id,
    )


def _first_fit(
    lattice: Lattice,
    occupied: list[list[bool]],
    token: PackingToken,
    pass_id: int,
    district: str,
) -> Reservation | None:
    ny = lattice.module_count_y()
    nx = lattice.module_count_x()
    for need_w, need_h, rotated in try_orientations(token):
        dc = _span_for(need_w, lattice.step)
        dr = _span_for(need_h, lattice.step)
        hole = f"{lattice.step * dc}x{lattice.step * dr}"
        for row in range(ny):
            for col in range(nx):
                placed = _place_at(
                    lattice, occupied, token, col, row,
                    need_w, need_h, rotated, pass_id,
                )
                packing_debug(
                    PackingStep.FIT, district=district,
                    **fit_fields(
                        token, hole, rotated,
                        "yes" if placed else "no",
                        PackingReason.OK if placed else PackingReason.REJECT_AXIS,
                    ),
                )
                if placed is not None:
                    return placed
    return None


def _center_module(inner: InnerBBox, lattice: Lattice) -> tuple[int, int] | None:
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


def _place_center(
    inner: InnerBBox,
    lattice: Lattice,
    occupied: list[list[bool]],
    token: PackingToken,
    district: str,
) -> Reservation | None:
    home = _center_module(inner, lattice)
    if home is None:
        return None
    home_c, home_r = home
    for need_w, need_h, rotated in try_orientations(token):
        dc = _span_for(need_w, lattice.step)
        dr = _span_for(need_h, lattice.step)
        col = max(0, min(home_c - dc // 2, lattice.module_count_x() - dc))
        row = max(0, min(home_r - dr // 2, lattice.module_count_y() - dr))
        placed = _place_at(
            lattice, occupied, token, col, row,
            need_w, need_h, rotated, 1,
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


def run_pass1(
    slot: DistrictSlot,
    inner: InnerBBox,
    lattice: Lattice,
    tokens: list[PackingToken],
    corridor_rects: tuple[Rect, ...],
) -> tuple[list[Reservation], list[PackingToken], list[list[bool]]]:
    district = slot.district_template.system_name
    occupied = _init_occupied(slot, lattice, corridor_rects)
    placed: list[Reservation] = []
    leftover: list[PackingToken] = []
    center_taken = False
    for token in _pass1_order(tokens):
        if token.position == POSITION_CENTER:
            if center_taken:
                leftover.append(token)
                packing_warning(
                    PackingStep.PASS1, district=district,
                    uid=token.uid, reserved=False, reason=PackingReason.CENTER,
                )
                continue
            reservation = _place_center(inner, lattice, occupied, token, district)
            if reservation is None:
                leftover.append(token)
                packing_warning(
                    PackingStep.PASS1, district=district,
                    uid=token.uid, reserved=False, reason=PackingReason.CENTER,
                )
                continue
            center_taken = True
            placed.append(reservation)
            packing_info(
                PackingStep.PASS1, district=district,
                uid=token.uid, reserved=True,
                span=f"{reservation.span_cols}x{reservation.span_rows}",
                reason=PackingReason.CENTER,
            )
            log_place(district, reservation)
            continue
        reservation = _first_fit(lattice, occupied, token, 1, district)
        if reservation is None:
            leftover.append(token)
            packing_warning(
                PackingStep.PASS1, district=district,
                uid=token.uid, reserved=False, reason=PackingReason.SKIP_NO_HOLE,
            )
            continue
        placed.append(reservation)
        packing_info(
            PackingStep.PASS1, district=district,
            uid=token.uid, reserved=True,
            span=f"{reservation.span_cols}x{reservation.span_rows}",
            reason=PackingReason.PLACE,
        )
        log_place(district, reservation)
    return placed, leftover, occupied
