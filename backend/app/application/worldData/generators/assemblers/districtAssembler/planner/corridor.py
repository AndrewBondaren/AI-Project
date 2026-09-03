"""Through-road corridor on the district lattice — C22 anchors."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.districtAssembler.connectionEntry import (
    ConnectionEntry,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    InnerBBox,
    Lattice,
    Rect,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_info,
)
from app.application.worldData.generators.road.widthResolver import resolve_width
from app.dataModel.settlement.enums.districtEntryRole import DistrictEntryRole


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
