"""PC-1: nominal identities, typed records and pure validation vocabulary."""

from dataclasses import FrozenInstanceError, dataclass
from enum import StrEnum
import subprocess
import sys
import unittest

from pydantic import TypeAdapter, ValidationError

from app.application.jsonValidation import types as legacy
from app.dataModel.cache.contracts.cacheContract import (
    CacheContract, CacheContractId, CacheContractMetadata, CacheContractRegistry, CacheSchemaVersion,
)
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup, CacheLookupStatus, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheItemKey, CacheKey
from app.dataModel.cache.policy.cachePolicy import CacheEvictionPolicy, CachePolicy
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency, PlanDependencyContract
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import (
    AlgorithmVersion, InputFingerprint, OutputFingerprint, PlanKey, PlanScope, PlanSlot,
    RegionPlanScope, SchemaVersion, WorldPlanScope,
)
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from app.dataModel.registryKey import RegistryKey, registry_key_target
from app.dataModel.validation.diagnostics import fieldPathError as shared
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex, RuntimeIssueContext
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


@dataclass(frozen=True)
class ClimatePayload:
    temperatures: tuple[int, ...]


@dataclass(frozen=True)
class HydroPayload:
    depths: tuple[int, ...]


class Action(StrEnum):
    DISABLE = "disable"


class Reason(StrEnum):
    INVALID = "invalid"


def plan_key(**update):
    return PlanKey.model_validate({"world_uid": "world", "scope": WorldPlanScope(),
        "contract_id": "surface.climate_base", "schema_version": 1, "algorithm_version": 1,
        "input_fingerprint": bytes(32)} | update)


def plan_ref(**update):
    return PlanRef(key=plan_key(**update), output_fingerprint=OutputFingerprint(bytes(32)))


class PlanningContractTests(unittest.TestCase):
    def test_scopes_are_tagged_and_required_values_are_not_defaulted(self):
        adapter = TypeAdapter(PlanScope)
        self.assertIsInstance(adapter.validate_python({"kind": "world"}), WorldPlanScope)
        self.assertIsInstance(adapter.validate_python({"kind": "region", "region_uid": "r"}), RegionPlanScope)
        for invalid in ({}, {"kind": "tile"}, {"kind": "region"},
                        {"kind": "region", "region_uid": " "}, {"kind": "world", "tile": 1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                adapter.validate_python(invalid)

    def test_key_strict_versions_and_digest(self):
        for name, values in (
            ("world_uid", ("", " world", "world ", 12)),
            ("schema_version", (0, -1, True, "1", 1.0)),
            ("algorithm_version", (0, False, "1")),
            ("input_fingerprint", (b"", bytes(31), bytes(33), "a" * 32, bytearray(32))),
            ("contract_id", ("", 123)),
        ):
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValidationError):
                    plan_key(**{name: value})
        self.assertEqual(plan_key().input_fingerprint, bytes(32))
        for bad in (bytes(31), bytes(33), "a" * 32):
            with self.assertRaises(ValidationError):
                PlanRef.model_validate({"key": plan_key(), "output_fingerprint": bad})

    def test_metadata_registries_reject_duplicates_and_keep_nominal_targets(self):
        meta = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("surface.climate_base"),
                                   schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))
        self.assertEqual(PlanContractRegistry(entries=(meta,)).entries, (meta,))
        with self.assertRaises(ValidationError):
            PlanContractRegistry(entries=(meta, meta))
        cache_meta = CacheContractMetadata(id=RegistryKey[CacheContractRegistry]("envelope"),
                                           schema_version=CacheSchemaVersion(1))
        self.assertEqual(CacheContractRegistry(entries=(cache_meta,)).entries, (cache_meta,))
        with self.assertRaises(ValidationError):
            CacheContractRegistry(entries=(cache_meta, cache_meta))
        self.assertIs(registry_key_target(PlanKey.model_fields["contract_id"].annotation), PlanContractRegistry)
        self.assertIs(registry_key_target(CacheContractId), CacheContractRegistry)

    def test_dependency_slots_and_metadata(self):
        dep = PlanDependency(slot=PlanSlot("climate_base"), ref=plan_ref())
        declaration = PlanDependencyContract(slot=dep.slot, contract_id=dep.ref.key.contract_id,
            schema_version=dep.ref.key.schema_version, algorithm_version=dep.ref.key.algorithm_version)
        self.assertTrue(declaration.accepts(dep))
        for field, value in (("contract_id", "surface.hydrology"), ("schema_version", 2), ("algorithm_version", 2)):
            self.assertFalse(declaration.accepts(PlanDependency(slot=dep.slot, ref=plan_ref(**{field: value}))))
        request = PlanRequest[ClimatePayload](key=plan_key(), inputs=ClimatePayload((10,)), dependencies=(dep,))
        self.assertEqual(request.dependencies, (dep,))
        other = PlanDependency(slot=PlanSlot("terrain_base"), ref=plan_ref())
        for deps in ((dep, dep), (other, dep)):
            with self.assertRaises(ValidationError):
                PlanRequest[ClimatePayload](key=plan_key(), inputs=ClimatePayload((10,)), dependencies=deps)
            with self.assertRaises(ValidationError):
                PlanEnvelope[ClimatePayload](ref=plan_ref(), dependencies=deps, payload=ClimatePayload((10,)), diagnostics=())
        with self.assertRaises(ValidationError):
            PlanDependency(slot=PlanSlot(""), ref=plan_ref())

    def test_namespace_revision_and_scope_are_part_of_identity(self):
        original = plan_key()
        for update in ({"input_fingerprint": bytes([1]) * 32}, {"contract_id": "surface.hydrology"},
                       {"schema_version": 2}, {"algorithm_version": 2}, {"world_uid": "another"},
                       {"scope": RegionPlanScope(region_uid="region")}):
            self.assertNotEqual(original, plan_key(**update))
        self.assertNotEqual(plan_ref(), PlanRef(key=original, output_fingerprint=OutputFingerprint(bytes([1]) * 32)))

    def test_immutable_payload_envelope_and_existing_instance_revalidation(self):
        payload = ClimatePayload((10, 20))
        result = PlanBuildResult[ClimatePayload](payload=payload, diagnostics=())
        envelope = PlanEnvelope[ClimatePayload](ref=plan_ref(), dependencies=(), payload=result.payload, diagnostics=())
        with self.assertRaises(ValidationError):
            envelope.payload = ClimatePayload(())
        with self.assertRaises(FrozenInstanceError):
            envelope.payload.temperatures = ()
        with self.assertRaises(TypeError):
            envelope.payload.temperatures[0] = 99
        with self.assertRaises(ValidationError):
            PlanEnvelope[ClimatePayload].model_validate(envelope.model_copy(update={"dependencies": []}))
        for bad in (plan_key().model_copy(update={"schema_version": True}),
                    PlanKey.model_construct(**(plan_key().model_dump() | {"input_fingerprint": bytes(1)}))):
            with self.assertRaises(ValidationError):
                PlanKey.model_validate(bad)

    def test_shared_issue_symbols_and_runtime_context(self):
        for name in ("FieldPathError", "ReferenceIssueContext", "ReferenceIssueReason"):
            self.assertIs(getattr(legacy, name), getattr(shared, name))
        self.assertEqual(TypeAdapter(RevisionHex).validate_python("a" * 64), "a" * 64)
        for invalid in ("A" * 64, "a" * 63, "z" * 64, bytes(32)):
            with self.assertRaises(ValidationError):
                TypeAdapter(RevisionHex).validate_python(invalid)
        context = RuntimeIssueContext[Action, Reason](world_uid="w", snapshot_uid=None,
            content_revision=None, source_uid=None, body_uids=(), cell=None, face=None,
            fallback_action=Action.DISABLE, fallback_reason=Reason.INVALID)
        issue = shared.FieldPathError(("terrain", 0), "invalid", runtime_context=context)
        self.assertEqual(legacy.import_validation_http_detail(legacy.ImportValidationError([issue])),
                         [{"loc": ["terrain", 0], "msg": "invalid", "code": "VALIDATION_ERROR"}])
        diagnostic = PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.FALLBACK)
        self.assertEqual(diagnostic.issue.runtime_context, context)
        with self.assertRaises(FrozenInstanceError):
            context.source_uid = "changed"
        valid = dict(world_uid="w", snapshot_uid=None, content_revision=None, source_uid=None,
                     body_uids=(), cell=None, face=None, fallback_action=Action.DISABLE,
                     fallback_reason=Reason.INVALID)
        for invalid in ({"body_uids": []}, {"cell": (True, 0)}, {"fallback_action": "disable"},
                        {"content_revision": "F" * 64}, {"world_uid": " w"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                RuntimeIssueContext[Action, Reason](**(valid | invalid))
        with self.assertRaises(ValidationError):
            RuntimeIssueContext[Action, Reason](world_uid="w")
        self.assertEqual([mode.value for mode in ResolutionMode], ["runtime", "validate_only"])

    def test_modules_import_from_either_public_entry_without_application(self):
        for module in ("app.dataModel.planning.identity.planKey", "app.dataModel.planning.contracts.planContract",
                       "app.dataModel.cache.contracts.cacheLookup"):
            script = (f"import importlib,sys; importlib.import_module('{module}'); "
                      "assert not any(n.startswith('app.application') for n in sys.modules)")
            result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class CacheContractTests(unittest.TestCase):
    def contract(self, **update):
        return CacheContract[ClimatePayload].model_validate({"id": "climate", "schema_version": 1} | update)

    def test_entry_and_lookup_keep_t_and_hit_miss_shape(self):
        key = CacheKey[ClimatePayload](contract=self.contract(), item_key=CacheItemKey(bytes(32)))
        entry = CacheEntry[ClimatePayload](key=key, value=ClimatePayload((10,)))
        adapter = TypeAdapter(CacheLookup[ClimatePayload])
        hit = adapter.validate_python({"status": "hit", "entry": entry})
        self.assertIsInstance(hit, CacheHit)
        self.assertEqual(hit.entry.value.temperatures, (10,))
        miss = adapter.validate_python({"status": "miss"})
        self.assertIsInstance(miss, CacheMiss)
        self.assertEqual(miss.status, CacheLookupStatus.MISS)
        self.assertFalse(hasattr(miss, "entry"))
        for invalid in ({"status": "hit"}, {"status": "hit", "entry": None},
                        {"status": "miss", "entry": entry}, {"status": "failure"}):
            with self.assertRaises(ValidationError):
                adapter.validate_python(invalid)
        with self.assertRaises(ValidationError):
            CacheEntry[ClimatePayload].model_validate({"key": key, "value": HydroPayload((5,))})

    def test_cache_identity_is_separate_from_planning_and_versions_are_strict(self):
        key = CacheKey[ClimatePayload](contract=self.contract(), item_key=CacheItemKey(bytes(32)))
        for contract in (self.contract(id="hydro"), self.contract(schema_version=2)):
            self.assertNotEqual(key, CacheKey[ClimatePayload](contract=contract, item_key=key.item_key))
        for bad in (True, 0, -1, "1"):
            with self.assertRaises(ValidationError):
                self.contract(schema_version=bad)
        for bad in (bytes(31), bytes(33), "x" * 32):
            with self.assertRaises(ValidationError):
                CacheKey[ClimatePayload].model_validate({"contract": self.contract(), "item_key": bad})

    def test_resource_limits_are_required_positive_and_ttl_disabled(self):
        cache = CachePolicy(max_retained_bytes=100, max_entry_bytes=50)
        self.assertEqual(cache.eviction, CacheEvictionPolicy.LRU)
        self.assertIsNone(cache.ttl_seconds)
        for wire in ({}, {"max_retained_bytes": 100}, {"max_retained_bytes": 10, "max_entry_bytes": 11},
                     {"max_retained_bytes": 100, "max_entry_bytes": True},
                     {"max_retained_bytes": "100", "max_entry_bytes": 10},
                     {"max_retained_bytes": 100, "max_entry_bytes": 10, "ttl_seconds": 1}):
            with self.assertRaises(ValidationError):
                CachePolicy.model_validate(wire)
        self.assertEqual(PlanningExecutionPolicy(max_workers=2, max_pending_builds=4).max_workers, 2)
        for wire in ({}, {"max_workers": 0, "max_pending_builds": 2},
                     {"max_workers": True, "max_pending_builds": 2},
                     {"max_workers": 2, "max_pending_builds": -1}):
            with self.assertRaises(ValidationError):
                PlanningExecutionPolicy.model_validate(wire)


if __name__ == "__main__":
    unittest.main()
