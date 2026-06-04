"""
Footprint functions for each v1 shape_type.

All functions return a set of (x, y) integer tuples — interior cells of the room.
Walls are NOT included; they are computed by the cell generation pass from the footprint.

Coordinate convention:
  x increases east, y increases north.
  (x0, y0) = southwest corner of the bounding box.
"""

import math


def footprint_rectangle(x0: int, y0: int, width: int, depth: int) -> set[tuple[int, int]]:
    return {(x, y) for x in range(x0, x0 + width) for y in range(y0, y0 + depth)}


def footprint_square(x0: int, y0: int, width: int, depth: int) -> set[tuple[int, int]]:
    side = min(width, depth)
    return footprint_rectangle(x0, y0, side, side)


def footprint_circle(x0: int, y0: int, width: int, **_) -> set[tuple[int, int]]:
    r = width / 2
    cx = x0 + r - 0.5
    cy = y0 + r - 0.5
    r2 = r * r
    cells = set()
    for x in range(x0, x0 + width):
        for y in range(y0, y0 + width):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                cells.add((x, y))
    return cells


def footprint_semicircle(x0: int, y0: int, width: int, **_) -> set[tuple[int, int]]:
    """Flat wall on south side (y = y0); dome opens north."""
    r = width / 2
    cx = x0 + r - 0.5
    cy = y0 - 0.5          # flat cut at y0
    r2 = r * r
    cells = set()
    for x in range(x0, x0 + width):
        for y in range(y0, y0 + math.ceil(r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                cells.add((x, y))
    return cells


def footprint_semi_oval(x0: int, y0: int, width: int, depth: int, **_) -> set[tuple[int, int]]:
    """Flat wall on south side (y = y0); oval opens north. a = width/2, b = depth."""
    a = width / 2
    b = depth
    cx = x0 + a - 0.5
    cy = y0 - 0.5
    cells = set()
    for x in range(x0, x0 + width):
        for y in range(y0, y0 + depth + 1):
            dx = (x - cx) / a
            dy = (y - cy) / b
            if dx * dx + dy * dy <= 1.0:
                cells.add((x, y))
    return cells


def footprint_l_shape(
    x0: int, y0: int, width: int, depth: int,
    arm_width: int, arm_depth: int, arm_corner: str,
) -> set[tuple[int, int]]:
    """
    R1 (main body: width × depth) ∪ R2 (arm) at the specified corner.
    arm_corner: "northeast" | "northwest" | "southeast" | "southwest"
    """
    main = footprint_rectangle(x0, y0, width, depth)

    if arm_corner == "northeast":
        ax, ay = x0 + width - arm_width, y0 + depth - arm_depth
    elif arm_corner == "northwest":
        ax, ay = x0, y0 + depth - arm_depth
    elif arm_corner == "southeast":
        ax, ay = x0 + width - arm_width, y0
    else:  # southwest (default)
        ax, ay = x0, y0

    arm = footprint_rectangle(ax, ay, arm_width, arm_depth)
    return main | arm


def footprint_t_shape(
    x0: int, y0: int, width: int, depth: int,
    stem_width: int, stem_wall: str,
) -> set[tuple[int, int]]:
    """
    Horizontal beam (width × depth) ∪ stem centred on stem_wall.
    stem_depth uses the same depth as the beam; beam_depth = arm_depth parameter reserved for v2.
    For now: beam occupies the full bounding box minus the stem already inside it.
    T-shape: beam (width × depth) + stem extending beyond one wall.

    stem_wall: "north" | "south" | "east" | "west"
    Stem extends OUTWARD from the beam — stem_depth = depth (symmetric).
    """
    beam = footprint_rectangle(x0, y0, width, depth)

    stem_cx = x0 + width // 2
    stem_cy = y0 + depth // 2

    if stem_wall == "south":
        sx = stem_cx - stem_width // 2
        sy = y0 - depth
        stem = footprint_rectangle(sx, sy, stem_width, depth)
    elif stem_wall == "north":
        sx = stem_cx - stem_width // 2
        sy = y0 + depth
        stem = footprint_rectangle(sx, sy, stem_width, depth)
    elif stem_wall == "west":
        sx = x0 - depth
        sy = stem_cy - stem_width // 2
        stem = footprint_rectangle(sx, sy, depth, stem_width)
    else:  # east
        sx = x0 + width
        sy = stem_cy - stem_width // 2
        stem = footprint_rectangle(sx, sy, depth, stem_width)

    return beam | stem


# ---------------------------------------------------------------------------
# Dispatch

def room_footprint(
    shape_type: str,
    x0: int,
    y0: int,
    width: int,
    depth: int,
    shape_params: dict | None = None,
) -> set[tuple[int, int]]:
    """
    Main entry point. Returns interior cell set for the given shape.
    shape_params used by l_shape and t_shape.
    """
    p = shape_params or {}

    if shape_type == "rectangle":
        return footprint_rectangle(x0, y0, width, depth)
    if shape_type == "square":
        return footprint_square(x0, y0, width, depth)
    if shape_type == "circle":
        return footprint_circle(x0, y0, width)
    if shape_type == "semicircle":
        return footprint_semicircle(x0, y0, width)
    if shape_type == "semi_oval":
        return footprint_semi_oval(x0, y0, width, depth)
    if shape_type == "l_shape":
        return footprint_l_shape(
            x0, y0, width, depth,
            arm_width=p.get("arm_width", max(2, width // 3)),
            arm_depth=p.get("arm_depth", max(2, depth // 3)),
            arm_corner=p.get("arm_corner", "northeast"),
        )
    if shape_type == "t_shape":
        return footprint_t_shape(
            x0, y0, width, depth,
            stem_width=p.get("stem_width", max(2, width // 3)),
            stem_wall=p.get("stem_wall", "south"),
        )
    raise ValueError(f"Unknown shape_type: {shape_type!r}")
