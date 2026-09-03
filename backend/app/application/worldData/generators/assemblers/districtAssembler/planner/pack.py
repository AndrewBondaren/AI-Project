"""C22 tokens + two-pass AABB packing on the district lattice."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.geometry import (
    module_blocked_by_corridor,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    Hole,
    InnerBBox,
    Lattice,
    PackingToken,
    Reservation,
)
from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
    BuildingLayoutCache,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_debug,
    packing_info,
    packing_warning,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    lookup_building_template,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    building_tier_compatible,
)
from app.dataModel.settlement.district.requiredStructure import POSITION_CENTER, RequiredStructure
from app.dataModel.settlement.district.structurePlacement import (
    resolve_structure_count,
    resolve_structure_priority,
)
from app.dataModel.spatial.facing import Facing
from app.db.models.world import World

YARD_PADDING_M = 1

Rect = tuple[int, int, int, int]


def _parcel_size(w: int, h: int, rotated: bool) -> tuple[int, int]:
    pad = 2 * YARD_PADDING_M
    if rotated:
        return h + pad, w + pad
    return w + pad, h + pad


def _span_for(size: int, step: int) -> int:
    return max(1, (size + step - 1) // step)


def _rect_fits(need_w: int, need_h: int, rect: Rect) -> bool:
    x0, y0, x1, y1 = rect
    return (x1 - x0) >= need_w and (y1 - y0) >= need_h


def candidate_template_names(
    slot: DistrictSlot,
    cache: BuildingLayoutCache,
    world: World,
    skeleton: CitySkeleton,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for req in slot.required_structures:
        name = req.building_template
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    allowed = slot.district_template.allowed_structure_types
    if allowed:
        for name in cache.template_names():
            if name in seen:
                continue
            template = lookup_building_template(world, name)
            if template is None:
                continue
            if not building_tier_compatible(template, skeleton, world):
                continue
            st = template.get("structure_type") or template.get("system_type")
            if st in allowed:
                names.append(name)
                seen.add(name)
    return names


def _required_for(slot: DistrictSlot, system_name: str) -> RequiredStructure | None:
    for req in slot.required_structures:
        if req.building_template == system_name:
            return req
    return None


def build_tokens(
    slot: DistrictSlot,
    cache: BuildingLayoutCache,
    world: World,
    skeleton: CitySkeleton,
) -> list[PackingToken]:
    district = slot.district_template.system_name
    names = candidate_template_names(slot, cache, world, skeleton)
    if not names:
        packing_warning(
            PackingStep.CACHE, district=district, reason=PackingReason.NO_CANDIDATES,
        )
    tokens: list[PackingToken] = []
    for name in names:
        fp = cache.envelope(name)
        template = lookup_building_template(world, name)
        if fp is None or template is None:
            packing_warning(
                PackingStep.CACHE, district=district,
                system_name=name, reason=PackingReason.NO_CACHE,
            )
            continue
        packing_info(
            PackingStep.CACHE, district=district,
            system_name=name, facing=Facing.SOUTH,
            w=fp.width, h=fp.depth, hit=True,
        )
        required = _required_for(slot, name)
        n, n_from = resolve_structure_count(
            name,
            required=required,
            district_counts=slot.district_template.structure_counts,
            settlement_counts=skeleton.structure_counts,
        )
        priority = resolve_structure_priority(
            name,
            district_priority=slot.district_template.structure_priority,
            settlement_priority=skeleton.structure_priority,
        )
        position = required.position if required is not None else None
        if n <= 0:
            packing_info(
                PackingStep.TOKENS, district=district,
                uid=f"{name}#0", w=fp.width, h=fp.depth,
                N=0, priority=priority, n_from=n_from,
            )
            continue
        for i in range(n):
            token = PackingToken(
                uid=f"{name}#{i}",
                system_name=name,
                w=fp.width,
                h=fp.depth,
                priority=priority,
                required=required is not None,
                position=position,
                copy_index=i,
                n_from=n_from,
            )
            tokens.append(token)
            packing_info(
                PackingStep.TOKENS, district=district,
                uid=token.uid, w=token.w, h=token.h,
                N=n, priority=priority, n_from=n_from,
            )
    return tokens


def _pass1_order(tokens: list[PackingToken]) -> list[PackingToken]:
    required = [t for t in tokens if t.required]
    rest = [t for t in tokens if (not t.required) and t.priority > 0]
    rest.sort(key=lambda t: (-t.priority, -max(t.w, t.h), -min(t.w, t.h), t.uid))
    return required + rest


def _pass2_tokens(tokens: list[PackingToken]) -> list[PackingToken]:
    return [t for t in tokens if (not t.required) and t.priority <= 0]


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


def _try_orientations(token: PackingToken) -> tuple[tuple[int, int, bool], ...]:
    a = _parcel_size(token.w, token.h, False)
    b = _parcel_size(token.w, token.h, True)
    first = (a[0], a[1], False)
    second = (b[0], b[1], True)
    if (first[0], first[1]) == (second[0], second[1]):
        return (first,)
    return (first, second)


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
    if not _rect_fits(need_w, need_h, rect):
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


def _fit_fields(
    token: PackingToken,
    hole: str,
    rotated: bool,
    fit: str,
    reason: PackingReason | None = None,
) -> dict:
    fields: dict = {
        "hole": hole,
        "token": token.uid,
        "try": 90 if rotated else 0,
        "fit": fit,
    }
    if reason is not None:
        fields["reason"] = reason
    return fields


def _first_fit(
    lattice: Lattice,
    occupied: list[list[bool]],
    token: PackingToken,
    pass_id: int,
    district: str,
) -> Reservation | None:
    ny = lattice.module_count_y()
    nx = lattice.module_count_x()
    for need_w, need_h, rotated in _try_orientations(token):
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
                    **_fit_fields(
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
    for need_w, need_h, rotated in _try_orientations(token):
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
            **_fit_fields(
                token, "center", rotated,
                "yes" if placed else "no",
                PackingReason.OK if placed else PackingReason.REJECT_AXIS,
            ),
        )
        if placed is not None:
            return placed
    return None


def _log_place(district: str, reservation: Reservation) -> None:
    token = reservation.token
    planted_w = token.h if reservation.rotated_90 else token.w
    planted_h = token.w if reservation.rotated_90 else token.h
    packing_info(
        PackingStep.PLACE, district=district,
        uid=token.uid,
        origin=reservation.rect_xy[:2],
        planted=f"{planted_w}x{planted_h}",
        facing=Facing.SOUTH,
        pass_id=reservation.pass_id,
    )


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
            _log_place(district, reservation)
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
        _log_place(district, reservation)
    return placed, leftover, occupied


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
            for need_w, need_h, rotated in _try_orientations(token):
                if not _rect_fits(need_w, need_h, rect):
                    packing_debug(
                        PackingStep.FIT, district=district,
                        **_fit_fields(token, hole_s, rotated, "no", PackingReason.REJECT_AXIS),
                    )
                    continue
                x0, y0, _, _ = rect
                used = (x0, y0, x0 + need_w, y0 + need_h)
                hole.free.pop(idx)
                hole.free.extend(_split_free(rect, used))
                packing_debug(
                    PackingStep.FIT, district=district,
                    **_fit_fields(token, hole_s, rotated, "yes", PackingReason.OK),
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
        _log_place(district, reservation)
    return placed, leftover
