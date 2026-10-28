"""Set algebra oracle for interval operations; strict/frozen wire contracts."""

from itertools import groupby, permutations
from random import Random
from unittest import TestCase

from pydantic import ValidationError

from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure as Measure
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage


def coverage(cells, uid="region"):
    spans = []
    for y, row in groupby(sorted(cells, key=lambda c: (c[1], c[0])), key=lambda c: c[1]):
        xs = [x for x, _ in row]
        for _, run in groupby(enumerate(xs), key=lambda pair: pair[1] - pair[0]):
            values = [x for _, x in run]
            spans.append(CoverageSpan(y=y, x0=values[0], x1=values[-1] + 1))
    return RegionCoverage(region_uid=uid, spans=tuple(spans))


def cells(value):
    return {(x, span.y) for span in value.spans for x in range(span.x0, span.x1)}


class CoverageTests(TestCase):
    def test_randomized_algebra_matches_sets_and_explicit_result_identity(self):
        rng = Random(718)
        domain = [(x, y) for y in range(-3, 4) for x in range(-5, 6)]
        for _ in range(60):
            a = {c for c in domain if rng.random() < 0.5}
            b = {c for c in domain if rng.random() < 0.4}
            left, right = coverage(a, "left"), coverage(b, "right")
            for operation, expected in ((lambda: Measure.union((left, right), region_uid="result"), a | b),
                                        (lambda: Measure.intersection(left, right, region_uid="result"), a & b),
                                        (lambda: Measure.subtract(left, right, region_uid="result"), a - b)):
                result = operation()
                self.assertEqual(cells(result), expected)
                self.assertEqual(Measure.area(result), len(expected))
                self.assertEqual(result.region_uid, "result")
                self.assertEqual(RegionCoverage.model_validate_json(result.model_dump_json()), result)

    def test_empty_union_and_permutations_have_no_implicit_uid(self):
        self.assertEqual(Measure.union((), region_uid="empty"), coverage(set(), "empty"))
        operands = (coverage({(0, 0), (1, 0)}, "a"), coverage({(1, 0), (2, 0)}, "b"), coverage({(3, 0)}, "c"))
        expected = coverage({(0, 0), (1, 0), (2, 0), (3, 0)}, "union")
        for order in permutations(operands):
            self.assertEqual(Measure.union(order, region_uid="union"), expected)
        with self.assertRaises(TypeError):
            Measure.union(operands)

    def test_malformed_or_noncanonical_spans_are_rejected(self):
        for raw in ({"y": True, "x0": 0, "x1": 2}, {"y": 0, "x0": 2, "x1": 2},
                    {"y": 0, "x0": 3, "x1": 2}, {"y": 0, "x0": 0.5, "x1": 2}):
            with self.assertRaises(ValidationError):
                CoverageSpan.model_validate(raw)
        for spans in ((CoverageSpan(y=1, x0=0, x1=2), CoverageSpan(y=0, x0=0, x1=2)),
                      (CoverageSpan(y=0, x0=0, x1=2), CoverageSpan(y=0, x0=2, x1=3)),
                      (CoverageSpan(y=0, x0=0, x1=3), CoverageSpan(y=0, x0=1, x1=4))):
            with self.assertRaises(ValidationError):
                RegionCoverage(region_uid="bad", spans=spans)

    def test_empty_coverage_and_frozen_values_are_valid(self):
        empty = coverage(set())
        self.assertEqual(Measure.area(empty), 0)
        with self.assertRaises(ValidationError):
            empty.region_uid = "other"
