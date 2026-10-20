"""Correlated boundary noise and interior falloff, separate from pure shapes."""

from collections.abc import Callable
from functools import cache
from math import hypot

from app.dataModel.spatial.regionShape import BboxShape, EllipseShape, PolygonShape, RegionShape
from app.dataModel.topology.worldTopology import WorldTopology


def smooth_field(sample: Callable[..., float], scale: int,
                 topology: WorldTopology) -> Callable[[int, int], float]:
    """Interpolate seeded lattice knots; fine and light use the same field."""
    @cache
    def knot(x: int, y: int) -> float:
        raw = x * scale, y * scale
        # Outside planar knots may support interpolation, but are never painted.
        coord = topology.canonicalize(*raw)
        if coord is None:
            coord = raw
        return sample(x=coord[0], y=coord[1])

    def value(x: int, y: int) -> float:
        ix, ox = divmod(x, scale)
        iy, oy = divmod(y, scale)
        sx, sy = ox / scale, oy / scale
        sx, sy = sx * sx * (3 - 2 * sx), sy * sy * (3 - 2 * sy)
        bottom = knot(ix, iy) * (1 - sx) + knot(ix + 1, iy) * sx
        top = knot(ix, iy + 1) * (1 - sx) + knot(ix + 1, iy + 1) * sx
        return bottom * (1 - sy) + top * sy

    return value


def boundary_depth(shape: RegionShape, x: int, y: int) -> float:
    """Interior distance used only for edge-noise decay, after contains()."""
    if isinstance(shape, BboxShape):
        return min(x - shape.x_min, shape.x_max - x, y - shape.y_min, shape.y_max - y)
    if isinstance(shape, EllipseShape):
        # Conservative normalized radial depth: no pruning beyond amplitude.
        radius = hypot((x - shape.cx) / shape.rx, (y - shape.cy) / shape.ry)
        return (1 - radius) * min(shape.rx, shape.ry)
    if isinstance(shape, PolygonShape):
        vertices = shape.vertices
        return min(_segment_distance(x, y, a, b)
                   for a, b in zip(vertices, vertices[1:] + vertices[:1]) if a != b)
    raise ValueError("anchor_radius must be resolved in collect before rasterization")


def _segment_distance(x: int, y: int, a: tuple[int, int], b: tuple[int, int]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
    return hypot(x - a[0] - t * dx, y - a[1] - t * dy)
