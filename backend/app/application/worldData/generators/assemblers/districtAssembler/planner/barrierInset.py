"""Barrier strips and inner bbox — C22 perimeter inset."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.lattice import (
    slot_rect,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    InnerBBox,
    Rect,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingHost,
    PackingReason,
    PackingStep,
    packing_info,
    packing_warning,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.barrierDefaults import (
    lookup_barrier_template,
)
from app.dataModel.settlement.area.perimeterBarrier import (
    PerimeterBarrier,
    resolved_host_sides,
)
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from app.db.models.world import World


def barrier_instance_valid(barrier: PerimeterBarrier | None) -> bool:
    if barrier is None:
        return False
    template = (barrier.template or "").strip()
    return bool(template)


def barrier_width_cells(
    barrier: PerimeterBarrier,
    world: World,
) -> int | None:
    template = lookup_barrier_template(world, barrier.template or "")
    if template is None:
        return None
    return int(template.width_cells)


def _inset_widths(
    barrier: PerimeterBarrier | None,
    world: World,
) -> tuple[dict[Facing, int], PackingReason, str | None, list[str]]:
    if not barrier_instance_valid(barrier):
        return {}, PackingReason.SKIP_NO_PERIMETER_BARRIER, None, []
    assert barrier is not None
    width = barrier_width_cells(barrier, world)
    if width is None:
        return {}, PackingReason.SKIP_NO_PERIMETER_BARRIER, barrier.template, []
    sides, skipped = resolved_host_sides(barrier)
    return {side: width for side in sides}, PackingReason.DISTRICT_BARRIER_ALWAYS, barrier.template, skipped


def _side_strip(rect: Rect, facing: Facing, width: int) -> Rect:
    x0, y0, x1, y1 = rect
    if facing is Facing.WEST:
        return (x0, y0, min(x1, x0 + width), y1)
    if facing is Facing.EAST:
        return (max(x0, x1 - width), y0, x1, y1)
    if facing is Facing.SOUTH:
        return (x0, y0, x1, min(y1, y0 + width))
    return (x0, max(y0, y1 - width), x1, y1)


def host_strips(rect: Rect, widths: dict[Facing, int]) -> list[Rect]:
    strips: list[Rect] = []
    for facing in CARDINAL_FACINGS:
        width = widths.get(facing, 0)
        if width > 0:
            strips.append(_side_strip(rect, facing, width))
    return strips


def subtract_strips(rect: Rect, strips: list[Rect]) -> Rect:
    x0, y0, x1, y1 = rect
    for sx0, sy0, sx1, sy1 in strips:
        if sx1 <= x0 or sx0 >= x1 or sy1 <= y0 or sy0 >= y1:
            continue
        if sx0 <= x0 and sx1 > x0 and sx1 < x1 and sy0 <= y0 and sy1 >= y1:
            x0 = sx1
        elif sx1 >= x1 and sx0 < x1 and sx0 > x0 and sy0 <= y0 and sy1 >= y1:
            x1 = sx0
        elif sy0 <= y0 and sy1 > y0 and sy1 < y1 and sx0 <= x0 and sx1 >= x1:
            y0 = sy1
        elif sy1 >= y1 and sy0 < y1 and sy0 > y0 and sx0 <= x0 and sx1 >= x1:
            y1 = sy0
    return (x0, y0, x1, y1)


def inset_rect(rect: Rect, widths: dict[Facing, int]) -> Rect:
    return subtract_strips(rect, host_strips(rect, widths))


def _log_barrier(
    district: str,
    reason: PackingReason,
    *,
    host: PackingHost | None = None,
    template: str | None = None,
    widths: dict[Facing, int] | None = None,
    skipped: list[str] | None = None,
    warning: bool = False,
    **extra: object,
) -> None:
    fields: dict[str, object] = {"reason": reason, **extra}
    if host is not None:
        fields["host"] = host
    if template is not None:
        fields["template"] = template
    if skipped:
        fields["skipped"] = skipped
    if widths:
        fields["sides"] = sorted(side.value for side in widths)
        fields["width_cells"] = next(iter(widths.values()))
    emit = packing_warning if warning else packing_info
    emit(PackingStep.DISTRICT_BARRIER, district=district, **fields)


def shrink_slot_by_settlement_barrier(
    slot: DistrictSlot,
    skeleton: CitySkeleton,
    world: World,
    footprint_x0: int,
    footprint_y0: int,
    side_m: int,
) -> None:
    """Subtract footprint barrier ∩ slot from district area. Mutates slot xy, not size_pct source."""
    widths, reason, template, skipped = _inset_widths(skeleton.perimeter_barrier, world)
    district = slot.district_template.system_name
    if reason is not PackingReason.DISTRICT_BARRIER_ALWAYS:
        _log_barrier(district, reason, host=PackingHost.SETTLEMENT)
        return
    fp = (footprint_x0, footprint_y0, footprint_x0 + side_m, footprint_y0 + side_m)
    before = slot_rect(slot)
    x0, y0, x1, y1 = subtract_strips(before, host_strips(fp, widths))
    slot.origin_x = x0
    slot.origin_y = y0
    slot.width_m = max(0, x1 - x0)
    slot.depth_m = max(0, y1 - y0)
    _log_barrier(
        district, PackingReason.SETTLEMENT_BARRIER_SHRINK,
        host=PackingHost.SETTLEMENT,
        template=template,
        widths=widths,
        skipped=skipped,
        before=before,
        after=slot_rect(slot),
    )


def district_barrier_widths(
    slot: DistrictSlot,
    world: World,
) -> tuple[dict[Facing, int], PackingReason, str | None, list[str]]:
    return _inset_widths(slot.district_template.perimeter_barrier, world)


def inner_edge_coords(
    slot: DistrictSlot,
    widths: dict[Facing, int],
) -> tuple[int, int, int, int]:
    """Inner face of district barrier strips on the (already settlement-shrunk) slot."""
    return inset_rect(slot_rect(slot), widths)


def inner_bbox_for_slot(
    slot: DistrictSlot,
    world: World,
) -> tuple[InnerBBox, dict[Facing, int], PackingReason]:
    widths, reason, template, skipped = district_barrier_widths(slot, world)
    district = slot.district_template.system_name
    if reason is not PackingReason.DISTRICT_BARRIER_ALWAYS:
        _log_barrier(district, reason)
        x0, y0, x1, y1 = slot_rect(slot)
        return InnerBBox(x0, y0, x1, y1), {}, reason
    _log_barrier(
        district, reason,
        template=template, widths=widths, skipped=skipped,
    )
    x0, y0, x1, y1 = inner_edge_coords(slot, widths)
    inner = InnerBBox(x0, y0, x1, y1)
    if inner.empty:
        _log_barrier(
            district, PackingReason.INNER_EMPTY,
            warning=True, bbox=inner.as_rect(),
        )
    return inner, widths, reason
