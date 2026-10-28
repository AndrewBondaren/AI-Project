"""Exact integer row conversion with existing membership; no fine-world cell array."""

from collections.abc import Callable, Iterator
from fractions import Fraction
from math import ceil, floor

from app.application.worldData.generators.terrain.regions.coverageMeasure import normalized_spans
from app.application.worldData.masks.regionRasterizer import geometry_membership
from app.application.worldData.masks.regionRasterNoise import boundary_depth
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.spatial.regionShape import (
    AnchorRadiusShape, BboxShape, CorridorShape, EllipseShape, PolygonShape, RegionShape,
)
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldTopology import Coord, WorldTopology


def _convex_run(shape: RegionShape, y: int, seed_x: float) -> tuple[int, int] | None:
    """Search the interval with the original predicate, including boundary integer points."""
    xmin, _, xmax, _ = shape.bbox()
    seed = next((x for x in (floor(seed_x), ceil(seed_x)) if xmin <= x <= xmax and shape.contains(x, y)), None)
    if seed is None:
        return None
    low, high = xmin, seed
    while low < high:
        mid = (low + high) // 2
        if shape.contains(mid, y):
            high = mid
        else:
            low = mid + 1
    start = low
    low, high = seed, xmax
    while low < high:
        mid = (low + high + 1) // 2
        if shape.contains(mid, y):
            low = mid
        else:
            high = mid - 1
    return start, low + 1


def _polygon_runs(shape: PolygonShape, y: int) -> Iterator[tuple[int, int]]:
    xmin, _, xmax, _ = shape.bbox()
    cuts = {xmin, xmax + 1}
    vertices = shape.vertices
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if min(a[1], b[1]) <= y <= max(a[1], b[1]):
            if a[1] == b[1]:
                crossings = (a[0], b[0])
            else:
                exact = Fraction(a[0]) + Fraction((y - a[1]) * (b[0] - a[0]), b[1] - a[1])
                # Include the same float crossing used by PolygonShape.contains as well.
                crossings = (exact, a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
            for crossing in crossings:
                cuts.update(x for x in (floor(crossing), ceil(crossing), floor(crossing) + 1, ceil(crossing) + 1)
                            if xmin <= x <= xmax + 1)
    ordered = sorted(cuts)
    for x0, x1 in zip(ordered, ordered[1:]):
        if shape.contains(x0, y):
            yield x0, x1


def _row_runs(shape: RegionShape, y: int) -> Iterator[tuple[int, int]]:
    if isinstance(shape, BboxShape):
        yield shape.x_min, shape.x_max + 1
    elif isinstance(shape, EllipseShape):
        run = _convex_run(shape, y, shape.cx)
        if run is not None:
            yield run
    elif isinstance(shape, PolygonShape):
        yield from _polygon_runs(shape, y)
    elif isinstance(shape, CorridorShape):
        for a, b in zip(shape.path, shape.path[1:]):
            if a == b:
                continue
            segment = CorridorShape(path=(a, b), width=shape.width)
            if a[1] == b[1]:
                seed_x = (a[0] + b[0]) / 2
            else:
                t = max(0, min(1, (y - a[1]) / (b[1] - a[1])))
                seed_x = a[0] + t * (b[0] - a[0])
            run = _convex_run(segment, y, seed_x)
            if run is not None:
                yield run
    else:
        raise ValueError("anchor_radius requires ready anchor before measurement")


def _geometry_runs(shape: RegionShape, y: int) -> tuple[CoverageSpan, ...]:
    spans = (CoverageSpan(y=FineY(y), x0=FineX(x0), x1=FineX(x1)) for x0, x1 in _row_runs(shape, y))
    return normalized_spans(sorted(spans, key=lambda s: s.x0))


def _noise_runs(shape: RegionShape, y: int, x0: int, x1: int, topology: WorldTopology,
                contains: Callable[[tuple[int, int], Coord], bool]) -> Iterator[tuple[int, int]]:
    edge = shape.edge_noise
    if edge is None or edge.amplitude == 0:
        yield x0, x1
        return
    # Interior depth is 1-Lipschitz for the existing boundary_depth predicates.
    # Whole spans proven farther than amplitude never sample noise; only boundary chunks split.
    stack = [(x0, x1)]
    while stack:
        start, end = stack.pop()
        mid = (start + end - 1) // 2
        if boundary_depth(shape, mid, y) >= edge.amplitude + max(mid - start, end - 1 - mid):
            yield start, end
        elif end - start == 1:
            canonical = topology.canonicalize(start, y)
            if canonical is not None and contains((start, y), canonical):
                yield start, end
        else:
            split = (start + end) // 2
            stack.append((split, end))
            stack.append((start, split))


def _canonical_run(y: int, x0: int, x1: int, topology: WorldTopology) -> Iterator[CoverageSpan]:
    bounds = topology.bounds
    if topology.mode is WorldTopologyMode.PLANAR:
        if not bounds.y_min <= y <= bounds.y_max:
            return
        x0, x1 = max(x0, bounds.x_min), min(x1, bounds.x_max + 1)
        if x0 >= x1:
            return
    start = topology.canonicalize(x0, y)
    end = topology.canonicalize(x1 - 1, y)
    if start is None or end is None:
        return
    if x1 - x0 >= bounds.width:
        intervals = ((bounds.x_min, bounds.x_max + 1),)
    elif start[0] <= end[0]:
        intervals = ((start[0], end[0] + 1),)
    else:
        intervals = ((bounds.x_min, end[0] + 1), (start[0], bounds.x_max + 1))
    for left, right in intervals:
        yield CoverageSpan(y=FineY(start[1]), x0=FineX(left), x1=FineX(right))


def coverage_for_shape(shape: RegionShape, *, root: str, region_uid: EntityUid,
                       topology: WorldTopology) -> RegionCoverage:
    if isinstance(shape, AnchorRadiusShape):
        raise ValueError("anchor_radius requires ready anchor before measurement")
    _, ymin, _, ymax = shape.bbox()
    if topology.mode is WorldTopologyMode.PLANAR:
        ymin, ymax = max(ymin, topology.bounds.y_min), min(ymax, topology.bounds.y_max)
    elif isinstance(shape, BboxShape) and (shape.edge_noise is None or shape.edge_noise.amplitude == 0):
        # Identical rectangle rows repeat within two world heights for both wrapped and sphere grids.
        # Canonical coordinates/reflections themselves still come only from WorldTopology.
        ymax = min(ymax, ymin + 2 * topology.bounds.height - 1)
    canonical_spans: list[CoverageSpan] = []
    for y in range(ymin, ymax + 1):
        # Noise's knot cache is row-scoped, so pathological boundary scans do not allocate a world cache.
        contains = geometry_membership(shape, root, region_uid, topology)
        row_spans: list[CoverageSpan] = []
        for span in _geometry_runs(shape, y):
            x0, x1 = span.x0, span.x1
            if topology.mode is WorldTopologyMode.PLANAR:
                x0, x1 = max(x0, topology.bounds.x_min), min(x1, topology.bounds.x_max + 1)
            if x0 >= x1:
                continue
            for start, end in _noise_runs(shape, y, x0, x1, topology, contains):
                row_spans.extend(_canonical_run(y, start, end, topology))
        canonical_spans.extend(normalized_spans(sorted(row_spans, key=lambda s: (s.y, s.x0))))
    return RegionCoverage(region_uid=region_uid,
        spans=normalized_spans(sorted(canonical_spans, key=lambda s: (s.y, s.x0))))
