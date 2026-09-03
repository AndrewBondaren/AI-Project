"""C22 pass 2 — leftover collection into empty modules after the street frame."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.parcel import (
    fit_fields,
    log_place,
    rect_fits,
    try_orientations,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    Hole,
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


def _pass2_tokens(tokens: list[PackingToken]) -> list[PackingToken]:
    return [t for t in tokens if (not t.required) and t.priority <= 0]


def holes_after_frame(
    lattice: Lattice,
    occupied: list[list[bool]],
) -> list[Hole]:
    holes: list[Hole] = []
    for row in range(lattice.module_count_y()):
        for col in range(lattice.module_count_x()):
            if occupied[row][col]:
                continue
            rect = lattice.module_rect(col, row)
            holes.append(Hole(col=col, row=row, rect=rect, free=[rect]))
    return holes


def _split_free(free: Rect, used: Rect) -> list[Rect]:
    fx0, fy0, fx1, fy1 = free
    _ux0, uy0, ux1, uy1 = used
    out: list[Rect] = []
    if ux1 < fx1:
        out.append((ux1, uy0, fx1, uy1))
    if uy1 < fy1:
        out.append((fx0, uy1, fx1, fy1))
    return [r for r in out if r[2] > r[0] and r[3] > r[1]]


def _place_in_holes(
    holes: list[Hole],
    token: PackingToken,
    district: str,
) -> Reservation | None:
    for hole in holes:
        for idx, rect in enumerate(list(hole.free)):
            hole_s = f"{rect[2] - rect[0]}x{rect[3] - rect[1]}"
            for need_w, need_h, rotated in try_orientations(token):
                if not rect_fits(need_w, need_h, rect):
                    packing_debug(
                        PackingStep.FIT, district=district,
                        **fit_fields(token, hole_s, rotated, "no", PackingReason.REJECT_AXIS),
                    )
                    continue
                x0, y0, _, _ = rect
                used = (x0, y0, x0 + need_w, y0 + need_h)
                hole.free.pop(idx)
                hole.free.extend(_split_free(rect, used))
                packing_debug(
                    PackingStep.FIT, district=district,
                    **fit_fields(token, hole_s, rotated, "yes", PackingReason.OK),
                )
                return Reservation(
                    token=token,
                    col=hole.col,
                    row=hole.row,
                    span_cols=1,
                    span_rows=1,
                    rect_xy=used,
                    rotated_90=rotated,
                    pass_id=2,
                )
    packing_info(
        PackingStep.PASS2, district=district,
        reason=PackingReason.EMPTY_LIST, uid=token.uid,
    )
    return None


def run_pass2(
    slot: DistrictSlot,
    tokens: list[PackingToken],
    holes: list[Hole],
) -> tuple[list[Reservation], list[PackingToken]]:
    district = slot.district_template.system_name
    placed: list[Reservation] = []
    leftover: list[PackingToken] = []
    remaining = _pass2_tokens(tokens)
    for token in remaining:
        reservation = _place_in_holes(holes, token, district)
        if reservation is None:
            leftover.append(token)
            packing_warning(
                PackingStep.LEFTOVER, district=district,
                uid=token.uid, reason=PackingReason.LEFTOVER,
            )
            continue
        placed.append(reservation)
        packing_info(
            PackingStep.PASS2, district=district,
            hole=f"{reservation.col},{reservation.row}",
            uid=token.uid,
        )
        log_place(district, reservation)
    return placed, leftover
