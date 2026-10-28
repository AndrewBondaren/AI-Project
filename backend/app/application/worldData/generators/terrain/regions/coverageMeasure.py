"""Interval algebra; result identity is always supplied by the caller (G3-R contract)."""

from collections.abc import Iterable, Iterator
from heapq import merge

from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineX
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage


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
    def area(coverage: RegionCoverage) -> int:
        return sum(span.x1 - span.x0 for span in coverage.spans)

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
