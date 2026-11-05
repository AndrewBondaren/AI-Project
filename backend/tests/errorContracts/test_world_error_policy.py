"""Error delivery policy at the world import and column entry points."""

import unittest
from unittest.mock import patch

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.terrainMasks.regions import ForestSpec


class WorldErrorPolicyTests(unittest.TestCase):
    def _context_with_degraded_region(self):
        ctx = ResolveContext(collect_only=True)
        spec = ForestSpec(shape=BboxShape(x_min=0, y_min=0, x_max=4, y_max=4))
        declared_region_identity("world-test", spec, ctx=ctx.child("region"))
        return ctx

    def test_collected_degradation_allows_valid_reference(self):
        ctx = self._context_with_degraded_region()
        world = normalize_world({"precipitation_liquid": "water"}, ctx=ctx)
        self.assertEqual(world["precipitation_liquid"], "water")
        self.assertEqual(ctx.errors, [])
        self.assertEqual([i.code.value for i in ctx.report.diagnostics], ["REGION_DEGRADED_IDENTITY"])

    def test_collected_degradation_does_not_hide_blocking_reference(self):
        ctx = self._context_with_degraded_region()
        with self.assertRaises(ImportValidationError) as caught:
            normalize_world({"precipitation_liquid": "absent"}, ctx=ctx)
        self.assertEqual([i.code.value for i in caught.exception.errors], ["REF_W_UNKNOWN"])
        self.assertEqual(caught.exception.errors, ctx.errors)
        self.assertEqual([i.code.value for i in ctx.report.diagnostics], ["REGION_DEGRADED_IDENTITY"])

    def test_rejection_collects_the_same_issue_and_emits_only_in_normal_execution(self):
        cases = (
            ("removed key", lambda ctx: normalize_world({"map_cell_size_m": 1}, ctx=ctx)),
            ("invalid slice", lambda ctx: normalize_world({"hydrology": "bad"}, ctx=ctx)),
            ("unknown column", lambda ctx: resolve_world_column("not_a_column", 1, ctx)),
            ("unknown reference", lambda ctx: normalize_world({"precipitation_liquid": "absent"}, ctx=ctx)),
        )
        for label, operation in cases:
            facts = []
            for preview, collect in ((False, False), (True, False), (False, True), (True, True)):
                with self.subTest(case=label, preview=preview, collect=collect):
                    ctx = ResolveContext.for_import(validate_only=preview)
                    ctx.collect_only = collect
                    with patch("app.application.jsonValidation.resolve.logger.warning") as warning:
                        with self.assertRaises(ImportValidationError) as caught:
                            operation(ctx)
                    self.assertEqual(ctx.errors, caught.exception.errors)
                    self.assertEqual(len(ctx.errors), 1)
                    self.assertEqual(warning.call_count, int(not preview and not collect))
                    facts.append(ctx.errors)
            self.assertTrue(all(issues == facts[0] for issues in facts))
