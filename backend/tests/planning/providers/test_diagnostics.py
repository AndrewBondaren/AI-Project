"""Diagnostics and technical failures remain identical on each delivery path."""

import unittest
from unittest.mock import patch

from app.application.cache.service.cacheService import CacheFailure
from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.planning.providers.test_domain_providers import Data, Harness, Provider, contract


class DiagnosticsTests(unittest.TestCase):
    def test_collect_only_inherits_without_changing_validation_policy(self):
        from app.application.jsonValidation.resolve import ResolveContext, report_issues, resolve_root_list
        from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
        for validate_only in (False, True):
            with self.subTest(validate_only=validate_only):
                ctx = ResolveContext(validate_only=validate_only, collect_only=True)
                child = ctx.child("water")
                self.assertTrue(child.collect_only)
                self.assertEqual(child.validate_only, validate_only)
                with self.assertNoLogs("app.application.jsonValidation.resolve", level="DEBUG"):
                    report_issues(child, [FieldPathError(("water",), "collected")])
                    resolve_root_list(WorldClimateZoneRegistry, [{"system_climate": "custom"}],
                        empty_factory=WorldClimateZoneRegistry.canonical_engine, label="test", ctx=child)
                self.assertEqual(len(ctx.errors), 1)

    def test_diagnostics_preserved_without_request_logging_on_hit_miss_rebuild(self):
        h = Harness()
        self.addCleanup(h.service.shutdown)
        diagnostics = tuple(PlanDiagnostic(issue=FieldPathError(("setting",), kind.value), disposition=kind)
                            for kind in PlanDiagnosticDisposition)
        provider = Provider(lambda *args: PlanBuildResult[Data](payload=Data(value=1), diagnostics=diagnostics))
        binding, _ = h.register(provider=provider)
        first = h.get(binding)
        self.assertEqual(first.diagnostics, diagnostics)
        self.assertEqual(h.get(binding), first)
        h.backend.clear()
        self.assertEqual(h.get(binding), first)
        self.assertEqual(provider.count, 2)

    def test_backend_failures_are_not_rebuilt_or_empty_domain_results(self):
        h = Harness()
        self.addCleanup(h.service.shutdown)
        binding, provider = h.register()
        with patch.object(h.backend, "get", side_effect=OSError("read failure")):
            with self.assertRaises(CacheFailure):
                h.get(binding)
        self.assertEqual(provider.count, 0)
        with patch.object(h.backend, "put", side_effect=OSError("write failure")):
            with self.assertRaises(CacheFailure):
                h.get(binding)
        self.assertEqual(provider.count, 1)
        self.assertEqual(h.backend.retained_bytes, 0)
        self.assertEqual(h.get(binding).payload.value, 4)

    def test_invalid_already_typed_provider_payload_is_not_admitted(self):
        h = Harness()
        self.addCleanup(h.service.shutdown)
        broken = Data(value=1).model_copy(update={"value": True})
        result = PlanBuildResult[Data].model_construct(payload=broken, diagnostics=())
        binding, _ = h.register(provider=Provider(lambda *args: result))
        with self.assertRaises(PlanBuildFailure):
            h.get(binding)
        self.assertEqual(h.backend.retained_bytes, 0)


if __name__ == "__main__":
    unittest.main()
