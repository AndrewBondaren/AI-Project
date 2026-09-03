"""Parcel size, 90° orientations, fit/place log — shared by C22 packing passes."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    PackingToken,
    Rect,
    Reservation,
    YARD_PADDING_M,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_info,
)
from app.dataModel.spatial.facing import Facing


def parcel_size(w: int, h: int, rotated: bool) -> tuple[int, int]:
    pad = 2 * YARD_PADDING_M
    if rotated:
        return h + pad, w + pad
    return w + pad, h + pad


def rect_fits(need_w: int, need_h: int, rect: Rect) -> bool:
    x0, y0, x1, y1 = rect
    return (x1 - x0) >= need_w and (y1 - y0) >= need_h


def try_orientations(token: PackingToken) -> tuple[tuple[int, int, bool], ...]:
    a = parcel_size(token.w, token.h, False)
    b = parcel_size(token.w, token.h, True)
    first = (a[0], a[1], False)
    second = (b[0], b[1], True)
    if (first[0], first[1]) == (second[0], second[1]):
        return (first,)
    return (first, second)


def fit_fields(
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


def log_place(district: str, reservation: Reservation) -> None:
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
