"""Interval algebra; result identity is always supplied by the caller (G3-R contract)."""

from collections.abc import Iterable, Iterator
from bisect import bisect_left
from heapq import merge
from itertools import groupby

from pydantic import TypeAdapter

from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, SurfaceGridCoord
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.topology.worldTopology import Coord

_CELLS = TypeAdapter(frozenset[Coord])


def normalized_spans(spans: Iterable[CoverageSpan]) -> tuple[CoverageSpan, ...]:
    result: list[CoverageSpan] = []
    for span in spans:
        if result and result[-1].y == span.y and span.x0 <= result[-1].x1:
            previous = result.pop()
            span = CoverageSpan(y=span.y, x0=previous.x0, x1=max(previous.x1, span.x1))
        result.append(span)
    return tuple(result)


class RegionCoverageMeasure:
    @staticmethod
    def from_cells(cells: frozenset[Coord], *, region_uid: EntityUid,
                   space: CoordinateSpace, grid: SurfaceGridSettings) -> RegionCoverage:
        """Project existing canonical cells to fine spans, without fine XY expansion."""
        cells = _CELLS.validate_python(cells, strict=True)
        grid = SurfaceGridSettings.model_validate(grid, strict=True)
        if not isinstance(space, CoordinateSpace) or space not in (
                CoordinateSpace.WORLD_SURFACE_GRID, CoordinateSpace.WORLD_FINE_GRID):
            raise ValueError("coverage requires world surface or world fine coordinate space")
        rows = normalized_spans(CoverageSpan(y=FineY(y), x0=FineX(x), x1=FineX(x + 1))
            for x, y in sorted(cells, key=lambda cell: (cell[1], cell[0])))
        if space is CoordinateSpace.WORLD_FINE_GRID:
            return RegionCoverage(region_uid=region_uid, spans=rows)
        expanded: list[CoverageSpan] = []
        for y, spans in groupby(rows, key=lambda span: span.y):
            row = tuple(spans)
            for dy in range(grid.fine_span):
                expanded.extend(CoverageSpan(y=FineY(y * grid.fine_span + dy),
                    x0=FineX(span.x0 * grid.fine_span), x1=FineX(span.x1 * grid.fine_span)) for span in row)
        return RegionCoverage(region_uid=region_uid, spans=tuple(expanded))

    @staticmethod
    def area(coverage: RegionCoverage) -> int:
        return sum(span.x1 - span.x0 for span in coverage.spans)

    @staticmethod
    def coarse_cell_areas(coverage: RegionCoverage, cells: tuple[SurfaceGridCoord, ...],
                          grid: SurfaceGridSettings) -> tuple[int, ...]:
        """Exact fine² intersections, in caller cell order; no shape rasterization."""
        spans = coverage.spans
        rows = tuple(span.y for span in spans)
        side = grid.fine_span
        areas: list[int] = []
        for cell in cells:
            x0, y0 = cell.gx * side, cell.gy * side
            start, end = bisect_left(rows, y0), bisect_left(rows, y0 + side)
            areas.append(sum(max(0, min(spans[i].x1, x0 + side) - max(spans[i].x0, x0))
                             for i in range(start, end)))
        return tuple(areas)

    @staticmethod
    def union(coverages: tuple[RegionCoverage, ...], *, region_uid: EntityUid) -> RegionCoverage:
        ordered = merge(*(c.spans for c in coverages), key=lambda s: (s.y, s.x0))
        return RegionCoverage(region_uid=region_uid, spans=normalized_spans(ordered))

    @staticmethod
    def intersection(a: RegionCoverage, b: RegionCoverage, *, region_uid: EntityUid) -> RegionCoverage:
        result: list[CoverageSpan] = []
        i = j = 0
        while i < len(a.spans) and j < len(b.spans):
            left, right = a.spans[i], b.spans[j]
            if left.y == right.y:
                x0, x1 = max(left.x0, right.x0), min(left.x1, right.x1)
                if x0 < x1:
                    result.append(CoverageSpan(y=left.y, x0=x0, x1=x1))
            if (left.y, left.x1) <= (right.y, right.x1):
                i += 1
            else:
                j += 1
        return RegionCoverage(region_uid=region_uid, spans=tuple(result))

    @staticmethod
    def subtract(a: RegionCoverage, b: RegionCoverage, *, region_uid: EntityUid) -> RegionCoverage:
        def remaining() -> Iterator[CoverageSpan]:
            j = 0
            for left in a.spans:
                while j < len(b.spans) and (b.spans[j].y < left.y or
                        b.spans[j].y == left.y and b.spans[j].x1 <= left.x0):
                    j += 1
                x = left.x0
                k = j
                while k < len(b.spans) and b.spans[k].y == left.y and b.spans[k].x0 < left.x1:
                    right = b.spans[k]
                    if x < right.x0:
                        yield CoverageSpan(y=left.y, x0=x, x1=min(right.x0, left.x1))
                    x = FineX(max(x, right.x1))
                    if x >= left.x1:
                        break
                    k += 1
                if x < left.x1:
                    yield CoverageSpan(y=left.y, x0=x, x1=left.x1)
        return RegionCoverage(region_uid=region_uid, spans=tuple(remaining()))
