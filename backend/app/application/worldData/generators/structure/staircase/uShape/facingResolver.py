"""Resolve U-shape far-end from upper-level exterior floor cells (§2)."""
from app.dataModel.spatial.facing import (
    CARDINAL_WALL_OUTWARD_DELTA, CARDINAL_DELTA_TO_FACING, Facing, opposite,
)
from app.dataModel.structure.enums.buildingElement import StructureElement


def resolve_u_shape_facing(footprint: set[tuple[int, int]], cells: dict,
                           z_top: int, fallback: Facing) -> Facing:
    scores = {}
    for side, (dx, dy) in CARDINAL_WALL_OUTWARD_DELTA.items():
        exterior = {(x + dx, y + dy) for x, y in footprint
                    if (x + dx, y + dy) not in footprint}
        scores[side] = sum(1 for x, y in exterior
                           if (cell := cells.get((x, y, z_top))) is not None
                           and cell.system_building_element == StructureElement.FLOOR)
    best = max(scores.values())
    if best == 0:
        return fallback
    exits = [side for side, score in scores.items() if score == best]
    # Prefer authored exit on a tie, then clockwise from it. This consumes no
    # RNG and rotates with the author frame instead of favoring a global axis.
    preferred = opposite(fallback)
    dx, dy = CARDINAL_WALL_OUTWARD_DELTA[preferred]
    for _ in range(4):
        exit_side = CARDINAL_DELTA_TO_FACING[(dx, dy)]
        if exit_side in exits:
            return opposite(exit_side)
        dx, dy = dy, -dx
    raise AssertionError("positive floor score requires an exit side")
