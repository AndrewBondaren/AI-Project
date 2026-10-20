"""Unrolled surface geometry — tz_terrain_generation § Топология поверхности.

Segments are supplied in an unrolled frame, preserving their authored extent.
Queries are lifted into that frame; consumers canonicalize only at grid IO.
"""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from fractions import Fraction
from math import floor, fsum, isfinite

from app.dataModel.spatial.facing import CARDINAL_FACINGS, CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldTopology import Coord, WorldTopology

Scalar = int | float | Fraction
GeometryPoint = tuple[Scalar, Scalar]


@dataclass(frozen=True)
class UnrolledImage:
    coord: GeometryPoint
    invert_dy: bool


@dataclass(frozen=True)
class SegmentProjection:
    """Distance to the closed segment, unclamped t, and both points in its frame."""

    distance2: Fraction
    projection: Fraction
    image: UnrolledImage
    nearest: GeometryPoint


def _distance2(p: GeometryPoint, q: GeometryPoint) -> Scalar:
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2


def _periodic_values(value: Scalar, period: int, low: Scalar,
                     high: Scalar) -> Iterator[Scalar]:
    # Include the nearest exterior image on either side of the query interval.
    for offset in range(floor((low - value) // period),
                        floor((high - value) // period) + 2):
        yield value + offset * period


def _images_in_box(topology: WorldTopology, cell: GeometryPoint,
                   low: GeometryPoint, high: GeometryPoint) -> Iterator[UnrolledImage]:
    if topology.mode is WorldTopologyMode.PLANAR:
        yield UnrolledImage(cell, False)
        return
    bounds = topology.bounds
    x, y = cell
    if topology.mode is WorldTopologyMode.WRAPPED:
        families = ((x, y, bounds.height, False),)
    else:
        # Cell centers reflect about y_min - 1/2 (equivalently y_max + 1/2).
        families = (
            (x, y, 2 * bounds.height, False),
            (x + bounds.width // 2, 2 * bounds.y_min - 1 - y,
             2 * bounds.height, True),
        )
    for image_x, image_y, period_y, invert_dy in families:
        for ix in _periodic_values(image_x, bounds.width, low[0], high[0]):
            for iy in _periodic_values(image_y, period_y, low[1], high[1]):
                yield UnrolledImage((ix, iy), invert_dy)


def unrolled_images(topology: WorldTopology, cell: GeometryPoint, *,
                    anchor: GeometryPoint | None = None) -> tuple[UnrolledImage, ...]:
    """Local tiling images around anchor (cell by default), nearest first.

    Wrapped images include ±w/±h. Sphere uses period 2h and reflected
    half-turn images. Anchor may itself be arbitrarily far outside bounds.
    Ties use (y, x, invert_dy), independently of iteration/hash order.
    """
    anchor = cell if anchor is None else anchor
    bounds = topology.bounds
    # Cover adjacent tiles, including the nearest exterior image above anchor.
    # Sphere also supplies both reflected families around the anchor latitude.
    images = _images_in_box(topology, cell,
                            (anchor[0] - bounds.width, anchor[1] - bounds.height),
                            anchor)
    return tuple(sorted(images, key=lambda image: (
        _distance2(anchor, image.coord), image.coord[1], image.coord[0], image.invert_dy,
    )))


def dist2(topology: WorldTopology, p: GeometryPoint, q: GeometryPoint) -> Scalar:
    """Squared minimum Euclidean distance over topology images of q."""
    return _distance2(p, unrolled_images(topology, q, anchor=p)[0].coord)


def canonical_frame(topology: WorldTopology, points: Iterable[Coord], *,
                     anchor: Coord) -> tuple[Coord, ...]:
    """Move one unrolled geometry frame so anchor is canonical, preserving extent.

    All vertices share one translation/reflection. Independent endpoint wraps
    would change segment lengths and break connected paths. Planar void anchors
    leave the frame unchanged; rasterization clips each output cell instead.
    """
    canonical = topology.canonicalize(*anchor)
    if canonical is None:
        return tuple(points)
    image = unrolled_images(topology, canonical, anchor=anchor)[0]
    sign_y = -1 if image.invert_dy else 1
    return tuple((canonical[0] + x - anchor[0], canonical[1] + sign_y * (y - anchor[1]))
                 for x, y in points)


def nearest_on_segment(topology: WorldTopology, p: GeometryPoint,
                       a: GeometryPoint, b: GeometryPoint, *,
                       tie_breaker: Callable[[SegmentProjection], Scalar] | None = None) -> SegmentProjection:
    """Nearest image of p to unrolled [a,b], with unclamped projection t.

    Canonical endpoint pairs are not silently shortened: callers unwrap a
    seam-crossing endpoint with unrolled_images before supplying a segment.
    All images spanning the segment bbox are considered, even over multiple
    periods. Integer inputs retain exact Fraction distances and projections.
    A point segment has t=0. Equal distances minimize optional tie_breaker,
    then image (y,x,invert_dy); the policy never overrides a smaller distance.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    low = min(a[0], b[0]), min(a[1], b[1])
    high = max(a[0], b[0]), max(a[1], b[1])

    def project(image: UnrolledImage) -> SegmentProjection:
        cx, cy = image.coord[0] - a[0], image.coord[1] - a[1]
        t = Fraction(cx * dx + cy * dy) / Fraction(length2) if length2 else Fraction(0)
        clamped = min(Fraction(1), max(Fraction(0), t))
        nearest = a[0] + clamped * dx, a[1] + clamped * dy
        return SegmentProjection(Fraction(_distance2(image.coord, nearest)), t, image, nearest)

    results = [project(image) for image in _images_in_box(topology, p, low, high)]
    distance = min(result.distance2 for result in results)
    return min((result for result in results if result.distance2 == distance),
               key=lambda result: (tie_breaker(result) if tie_breaker else 0,
                                   result.image.coord[1], result.image.coord[0], result.image.invert_dy))


def centroid(topology: WorldTopology, cells: Iterable[GeometryPoint],
             weights: Iterable[float], anchor: GeometryPoint) -> tuple[float, float]:
    """Weighted mean after unwrapping each cell to its nearest anchor image.

    Empty/zero-total inputs and negative/nonfinite weights are invalid.
    The result stays unrolled; the caller decides whether to canonicalize it.
    """
    contributions: list[tuple[float, float, float]] = []
    for cell, weight in zip(cells, weights, strict=True):
        if not isfinite(weight) or weight < 0:
            raise ValueError("centroid weights must be finite and nonnegative")
        if weight:
            image = unrolled_images(topology, cell, anchor=anchor)[0].coord
            contributions.append((float(image[0]) * weight, float(image[1]) * weight, weight))
    total = fsum(item[2] for item in contributions)
    if not total:
        raise ValueError("centroid requires positive total weight")
    return (fsum(item[0] for item in contributions) / total,
            fsum(item[1] for item in contributions) / total)


def canonical_neighbors4(topology: WorldTopology, cell: Coord) -> tuple[Coord, ...]:
    """Four canonical cardinal neighbours; non-existent directions are dropped."""
    return tuple(
        neighbor.coord
        for facing in CARDINAL_FACINGS
        if (neighbor := topology.neighbor(*cell, facing)) is not None
    )


def neighbors4_unrolled(cell: Coord) -> tuple[Coord, Coord, Coord, Coord]:
    """Four unrolled steps; passability/canonical membership belong to caller."""
    x, y = cell

    def step(facing: Facing) -> Coord:
        dx, dy = CARDINAL_WALL_OUTWARD_DELTA[facing]
        return x + dx, y + dy

    return step(Facing.EAST), step(Facing.WEST), step(Facing.NORTH), step(Facing.SOUTH)
