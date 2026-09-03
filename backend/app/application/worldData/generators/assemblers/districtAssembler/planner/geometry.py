"""Barrier strips, lattice lines, inner bbox, through-road corridor — C22."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import (
    ConnectionEntry,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    InnerBBox,
    Lattice,
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
from app.application.worldData.generators.road.blockSize import block_size_for_density
from app.application.worldData.generators.road.widthResolver import resolve_width
from app.dataModel.settlement.area.perimeterBarrier import (
    PerimeterBarrier,
    resolved_host_sides,
)
from app.dataModel.settlement.enums.districtEntryRole import DistrictEntryRole
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from app.db.models.world import World

Rect = tuple[int, int, int, int]


def axis_lines(origin: int, end: int, step: int) -> list[int]:
    """Inclusive origin and end; intermediate ticks at ``step`` (no stretch)."""
    if end < origin:
        return []
    if end == origin:
        return [origin]
    step = max(1, int(step))
    lines = [origin]
    pos = origin + step
    while pos < end:
        lines.append(pos)
        pos += step
    if lines[-1] != end:
        lines.append(end)
    return lines


def make_lattice(inner: InnerBBox, step: int) -> Lattice:
    return Lattice(
        xs=tuple(axis_lines(inner.x0, inner.x1, step)),
        ys=tuple(axis_lines(inner.y0, inner.y1, step)),
        step=max(1, int(step)),
    )


def slot_rect(slot: DistrictSlot) -> Rect:
    return (
        slot.origin_x,
        slot.origin_y,
        slot.origin_x + slot.width_m,
        slot.origin_y + slot.depth_m,
    )


def district_step(slot: DistrictSlot, skeleton: CitySkeleton) -> int:
    density = slot.district_template.density or skeleton.settlement_density
    return block_size_for_density(density)


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


def thicken_axis_line(
    x0: int, y0: int, x1: int, y1: int, width: int,
) -> Rect:
    w = max(1, int(width))
    half = (w - 1) // 2
    if y0 == y1:
        lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
        return (lo, y0 - half, hi + 1, y0 - half + w)
    lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
    return (x0 - half, lo, x0 - half + w, hi + 1)


def corridor_rects_from_entries(
    slot: DistrictSlot,
    inner: InnerBBox,
) -> tuple[tuple[Rect, ...], PackingReason]:
    district = slot.district_template.system_name
    if not slot.entry_nodes:
        packing_info(
            PackingStep.ANCHORS,
            district=district,
            reason=PackingReason.SKIP_NO_ENTRY_NODES,
        )
        return (), PackingReason.SKIP_NO_ENTRY_NODES
    by_uid = {e.node.node_uid: e for e in slot.entry_nodes}
    processed: set[frozenset[str]] = set()
    rects: list[Rect] = []
    for entry in slot.entry_nodes:
        if entry.role != DistrictEntryRole.THROUGH_ROAD:
            continue
        if entry.paired_exit_uid is None:
            continue
        pair = frozenset((entry.node.node_uid, entry.paired_exit_uid))
        if pair in processed:
            continue
        processed.add(pair)
        other = by_uid.get(entry.paired_exit_uid)
        if other is None:
            continue
        width = resolve_width(entry.connection_type)
        if width is None:
            continue
        rects.append(thicken_axis_line(
            entry.node.x, entry.node.y, other.node.x, other.node.y, width,
        ))
    packing_info(
        PackingStep.ANCHORS,
        district=district,
        entry_nodes=len(slot.entry_nodes),
        through_pairs=len(processed),
        corridor_rects=len(rects),
        inner=inner.as_rect(),
    )
    return tuple(rects), PackingReason.OK


def line_cuts_module_interior(
    x0: int, y0: int, x1: int, y1: int,
    mx0: int, my0: int, mx1: int, my1: int,
) -> bool:
    """True if an axis-aligned centre-line goes through the open interior of a module."""
    if y0 == y1:
        y = y0
        if not (my0 < y < my1):
            return False
        lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
        return not (hi < mx0 or lo > mx1)
    if x0 == x1:
        x = x0
        if not (mx0 < x < mx1):
            return False
        lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
        return not (hi < my0 or lo > my1)
    return False


def module_blocked_by_corridor(
    lattice: Lattice,
    col: int,
    row: int,
    corridor: tuple[Rect, ...],
    entries: list[ConnectionEntry],
) -> bool:
    mx0, my0, mx1, my1 = lattice.module_rect(col, row)
    by_uid = {e.node.node_uid: e for e in entries}
    processed: set[frozenset[str]] = set()
    for entry in entries:
        if entry.role != DistrictEntryRole.THROUGH_ROAD or entry.paired_exit_uid is None:
            continue
        pair = frozenset((entry.node.node_uid, entry.paired_exit_uid))
        if pair in processed:
            continue
        processed.add(pair)
        other = by_uid.get(entry.paired_exit_uid)
        if other is None:
            continue
        if line_cuts_module_interior(
            entry.node.x, entry.node.y, other.node.x, other.node.y,
            mx0, my0, mx1, my1,
        ):
            return True
    _ = corridor
    return False
