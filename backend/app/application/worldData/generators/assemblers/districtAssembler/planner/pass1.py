"""C22 pass 1 — priority reservations on the district lattice."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.cluster import (
    place_center_cluster,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.corridor import (
    module_blocked_by_corridor,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.occupy import (
    place_at,
    span_for,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.parcel import (
    fit_fields,
    log_place,
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


def _pass1_order(tokens: list[PackingToken]) -> list[PackingToken]:
    required = [t for t in tokens if t.required]
    rest = [t for t in tokens if (not t.required) and t.priority > 0]
    rest.sort(key=lambda t: (-t.priority, -max(t.w, t.h), -min(t.w, t.h), t.uid))
    return required + rest


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
        dc = span_for(need_w, lattice.step)
        dr = span_for(need_h, lattice.step)
        hole = f"{lattice.step * dc}x{lattice.step * dr}"
        for row in range(ny):
            for col in range(nx):
                placed = place_at(
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
    ordered = _pass1_order(tokens)
    center_tokens = [token for token in ordered if token.position == POSITION_CENTER]
    rest_tokens = [token for token in ordered if token.position != POSITION_CENTER]
    cluster = place_center_cluster(inner, lattice, occupied, center_tokens, district)
    placed.extend(cluster.reservations)
    leftover.extend(cluster.leftover)
    for token in rest_tokens:
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
