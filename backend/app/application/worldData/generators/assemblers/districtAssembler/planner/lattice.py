"""District lattice ticks — C22 block_size grid. No stretch."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    InnerBBox,
    Lattice,
    Rect,
)
from app.application.worldData.generators.road.blockSize import block_size_for_density


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
