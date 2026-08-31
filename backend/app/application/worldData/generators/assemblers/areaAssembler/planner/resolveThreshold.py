"""Threshold topology: kind + cells. No street_xy, no ray, no z formula."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import (
    AreaThreshold,
    AreaThresholdKind,
)
from app.application.worldData.generators.barrier.perimeter import (
    bbox_from_cells,
    gate_on_facing_edge,
)
from app.dataModel.spatial.facing import Facing

Coord = tuple[int, int]


def facing_edge_cells(
    cells: list[Coord],
    facing: Facing,
) -> list[Coord]:
    if not cells:
        return []
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    if facing == Facing.SOUTH:
        edge_y = min(ys)
        return [(x, y) for x, y in cells if y == edge_y]
    if facing == Facing.NORTH:
        edge_y = max(ys)
        return [(x, y) for x, y in cells if y == edge_y]
    if facing == Facing.WEST:
        edge_x = min(xs)
        return [(x, y) for x, y in cells if x == edge_x]
    if facing == Facing.EAST:
        edge_x = max(xs)
        return [(x, y) for x, y in cells if x == edge_x]
    return facing_edge_cells(cells, Facing.SOUTH)


def plot_equals_house(
    slot_cells: list[Coord],
    house_cells: list[Coord] | None,
) -> bool:
    """Case 3: plot occupancy is the house (same bbox and cell count)."""
    if not slot_cells or not house_cells:
        return False
    return (
        bbox_from_cells(slot_cells) == bbox_from_cells(house_cells)
        and len(slot_cells) == len(house_cells)
    )


def resolve_threshold(
    slot: AreaSlot,
    *,
    has_barrier: bool,
    entry_xy: Coord | None = None,
    house_cells: list[Coord] | None = None,
) -> AreaThreshold:
    """
    Pick door / gate / parcel_edge. ``z`` is a placeholder; assembler fills median.

    1. Plot == house → door (street meets the door). Porch/tambour: not yet.
    2. Yard + barrier → gate on facing parcel edge (same cell as case 3's edge center).
    3. Yard, no barrier → parcel_edge at that same facing-center cell.
    """
    edge = facing_edge_cells(slot.cells, slot.facing)
    if plot_equals_house(slot.cells, house_cells):
        if entry_xy is not None and entry_xy in set(slot.cells):
            return AreaThreshold(kind=AreaThresholdKind.DOOR, cells=[entry_xy], z=0)
        if edge:
            return AreaThreshold(kind=AreaThresholdKind.DOOR, cells=[edge[len(edge) // 2]], z=0)
    if has_barrier and slot.cells:
        gate = gate_on_facing_edge(*bbox_from_cells(slot.cells), slot.facing)
        return AreaThreshold(kind=AreaThresholdKind.GATE, cells=[gate], z=0)
    if not edge:
        fallback = list(slot.cells[:1]) if slot.cells else [(0, 0)]
        return AreaThreshold(kind=AreaThresholdKind.PARCEL_EDGE, cells=fallback, z=0)
    mid = edge[len(edge) // 2]
    return AreaThreshold(kind=AreaThresholdKind.PARCEL_EDGE, cells=[mid], z=0)
