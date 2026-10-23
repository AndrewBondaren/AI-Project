"""Contract checks on HIT/MISS, dependency identity and rebuild determinism."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planFingerprints import cache_item_key
from app.application.planning.service.planningService import PlanContractFailure, PlanContractFailureReason, PlanBuildFailure
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.planning.contracts.planDependency import PlanDependency, PlanDependencyContract
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.identity.planKey import RegionPlanScope
from tests.planning.providers.test_domain_providers import Data, Harness, Provider, Wait, contract, request


class PlanningServiceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.service.shutdown)
        self.binding, self.provider = self.h.register()

    def failure(self, reason, action):
        with self.assertRaises(PlanContractFailure) as caught:
            action()
        self.assertEqual(caught.exception.reason, reason)

    def test_hit_clear_restart_and_input_change_have_same_frozen_semantics(self):
        first = self.h.get(self.binding)
        self.assertEqual(first.payload.value, 4)
        self.assertEqual(self.h.get(self.binding), first)
        self.assertEqual(self.provider.count, 1)
        self.h.backend.clear()
        self.assertEqual(self.h.get(self.binding), first)
        self.assertEqual(self.provider.count, 2)
        self.assertNotEqual(self.h.get(self.binding, value=3).ref, first.ref)
        other = Harness()
        self.addCleanup(other.service.shutdown)
        other.registry.register(self.binding, Provider())
        self.assertEqual(other.get(self.binding), first)

    def test_registry_rejects_duplicate_and_substituted_handles(self):
        with self.assertRaises(ValueError):
            self.h.registry.register(self.binding, Provider())
        fake = replace(self.binding, validate_inputs=lambda value: value)
        self.failure(PlanContractFailureReason.UNKNOWN_CONTRACT, lambda: self.h.get(fake))
        self.failure(PlanContractFailureReason.UNKNOWN_CONTRACT, lambda: self.h.get(contract("unknown")))

    def test_metadata_and_fingerprint_checked_before_even_a_warm_cache(self):
        self.h.get(self.binding)
        req = request(self.binding)
        for change in ({"input_fingerprint": bytes(32)}, {"algorithm_version": 2}, {"schema_version": 2}):
            forged = req.model_copy(update={"key": req.key.model_copy(update=change)})
            self.failure(PlanContractFailureReason.KEY_MISMATCH, lambda: self.h.get(self.binding, req=forged))
        invalid = req.model_copy(update={"inputs": Data(value=1).model_copy(update={"value": True})})
        self.failure(PlanContractFailureReason.INVALID_INPUT, lambda: self.h.get(self.binding, req=invalid))
        self.assertEqual(self.provider.count, 1)

    def _dependent(self):
        base = self.h.get(self.binding)
        slot = "base"
        declaration = PlanDependencyContract(slot=slot, contract_id=self.binding.metadata.id,
            schema_version=1, algorithm_version=1)
        binding, provider = self.h.register(contract("test.dependent", declarations=(declaration,)),
            Provider(lambda req, deps, ctl: PlanBuildResult[Data](
                payload=Data(value=deps.require(slot, self.binding).payload.value + req.inputs.value), diagnostics=())))
        dep = PlanDependency(slot=slot, ref=base.ref)
        reader = self.h.empty.with_plan(slot, self.binding, base)
        return binding, provider, base, dep, reader

    def test_dependency_reader_validates_ref_payload_and_declared_slots_on_hit(self):
        binding, provider, base, dep, reader = self._dependent()
        req = request(binding, deps=(dep,))
        first = self.h.get(binding, req=req, dependencies=reader)
        self.assertEqual(first.payload.value, 6)
        self.assertEqual(self.h.get(binding, req=req, dependencies=reader), first)
        self.failure(PlanContractFailureReason.DEPENDENCY_MISMATCH,
                     lambda: self.h.get(binding, req=req, dependencies=self.h.empty))
        self.failure(PlanContractFailureReason.DEPENDENCY_MISMATCH,
                     lambda: self.h.get(binding, req=request(binding), dependencies=reader))
        newer = self.h.get(self.binding, value=9)
        wrong = self.h.empty.with_plan("base", self.binding, newer)
        self.failure(PlanContractFailureReason.DEPENDENCY_MISMATCH,
                     lambda: self.h.get(binding, req=req, dependencies=wrong))
        with self.assertRaises(PlanContractFailure):
            reader.require("undeclared", self.binding)
        self.assertEqual(provider.count, 1)
        updated = request(binding, deps=(PlanDependency(slot="base", ref=newer.ref),))
        self.assertNotEqual(self.h.get(binding, req=updated, dependencies=wrong).ref, first.ref)

    def test_foreign_world_scope_phase_and_extra_dependency_rejected(self):
        binding, _, base, dep, reader = self._dependent()
        for req in (request(binding, world="another", deps=(dep,)),
                    request(binding, scope=RegionPlanScope(region_uid="region"), deps=(dep,))):
            self.failure(PlanContractFailureReason.DEPENDENCY_MISMATCH,
                         lambda: self.h.get(binding, req=req, dependencies=reader))
        extra = reader.with_plan("extra", self.binding, base)
        self.failure(PlanContractFailureReason.DEPENDENCY_MISMATCH,
                     lambda: self.h.get(binding, req=request(binding, deps=(dep,)), dependencies=extra))
        wrong_phase = dep.model_copy(update={"ref": dep.ref.model_copy(update={
            "key": dep.ref.key.model_copy(update={"schema_version": 2})})})
        self.failure(PlanContractFailureReason.DEPENDENCY_MISMATCH,
            lambda: self.h.get(binding, req=request(binding, deps=(wrong_phase,)), dependencies=reader))

    def test_corrupt_output_digest_is_rejected_on_hit(self):
        envelope = self.h.get(self.binding)
        cachekey = CacheKey(contract=self.binding.cache_binding.contract,
            item_key=cache_item_key(envelope.ref.key, self.binding.manifest))
        corrupted = envelope.model_copy(update={"ref": envelope.ref.model_copy(update={"output_fingerprint": bytes(32)})})
        self.h.backend.put(CacheEntry(key=cachekey, value=corrupted))
        self.failure(PlanContractFailureReason.KEY_MISMATCH, lambda: self.h.get(self.binding))
        self.assertEqual(self.provider.count, 1)

    def test_provider_failure_not_cached_and_next_request_retries(self):
        binding, provider = self.h.register(contract("fails"), Provider(lambda *args: (_ for _ in ()).throw(ValueError("broken"))))
        for _ in range(2):
            with self.assertRaises(PlanBuildFailure) as caught:
                self.h.get(binding)
            self.assertTrue(caught.exception.issues)
        self.assertEqual(provider.count, 2)

    def test_oversize_delivered_unchanged_without_caching(self):
        from app.dataModel.cache.policy.cachePolicy import CachePolicy
        small = Harness(cache_policy=CachePolicy(max_retained_bytes=1, max_entry_bytes=1))
        self.addCleanup(small.service.shutdown)
        binding, provider = small.register()
        first = small.get(binding)
        self.assertEqual(first, small.get(binding))
        self.assertEqual(provider.count, 2)
        self.assertEqual(small.backend.retained_bytes, 0)

    def test_container_owns_one_registry_and_planning_service(self):
        from concurrent.futures import ThreadPoolExecutor
        from app.core.appSettings import app_settings
        from app.core.container import Container
        from tests.cache.test_admission import configured

        with patch.object(app_settings, "planning", configured()):
            container = Container(None, None)
            self.addCleanup(container.shutdown_planning)
            with ThreadPoolExecutor(max_workers=4) as pool:
                services = list(pool.map(lambda _: container.planning_service(), range(16)))
            self.assertTrue(all(service is services[0] for service in services))
            self.assertIs(container.plan_registry(), container.plan_registry())
            binding, provider = contract("container.test"), Provider()
            container.plan_registry().register(binding, provider)
            reader = PlanDependencyReader(container.plan_registry())
            result = services[0].get_or_build(binding, request(binding), reader, wait=Wait(2))
            self.assertEqual(result.payload.value, 4)
            self.assertEqual(services[0].get_or_build(binding, request(binding), reader, wait=Wait(2)), result)
            self.assertEqual(provider.count, 1)

    def test_missing_nested_default_field_is_not_silently_repaired(self):
        req = request(self.binding)
        scope = req.key.scope.model_copy()
        del scope.__dict__["kind"]
        broken = req.model_copy(update={"key": req.key.model_copy(update={"scope": scope})})
        self.failure(PlanContractFailureReason.INVALID_INPUT, lambda: self.h.get(self.binding, req=broken))

    def test_wrong_dependency_contract_handle_rejected_even_for_same_payload_shape(self):
        binding, _, base, dep, reader = self._dependent()
        another, _ = self.h.register(contract("other.phase"))
        self.failure(PlanContractFailureReason.DEPENDENCY_MISMATCH, lambda: reader.require("base", another))
