"""Canonical protocol vectors and reusable non-domain provider fixtures."""

from dataclasses import dataclass
from threading import Event, Lock
from time import monotonic
import unittest

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.encoding.canonicalCodec import CanonicalCodec
from app.application.planning.service.planFingerprints import input_fingerprint
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry, CanonicalTypeKind
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.service.cacheService import CacheService, retained_entry_bytes
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planningService import PlanningService, PlanWaitCancelled
from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.planning.contracts.planContract import PlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanKey, RegionPlanScope, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class Data(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    value: int = Field(ge=0)


MANIFEST = CanonicalSchemaManifest(entries=tuple(RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in (
        (1, Data, CanonicalTypeKind.RECORD), (2, PlanKey, CanonicalTypeKind.RECORD),
        (3, PlanRef, CanonicalTypeKind.RECORD), (4, WorldPlanScope, CanonicalTypeKind.RECORD),
        (5, RegionPlanScope, CanonicalTypeKind.RECORD), (6, type(WorldPlanScope().kind), CanonicalTypeKind.ENUM),
        (7, PlanDependency, CanonicalTypeKind.RECORD), (8, PlanDiagnostic, CanonicalTypeKind.RECORD),
        (9, PlanDiagnosticDisposition, CanonicalTypeKind.ENUM), (10, FieldPathError, CanonicalTypeKind.RECORD))))
CANONICAL = CanonicalCodec(MANIFEST)


class EnvelopeCodec:
    def validate(self, value: object) -> PlanEnvelope[Data]:
        return TypeAdapter(PlanEnvelope[Data]).validate_python(value, strict=True)

    def encode(self, value: PlanEnvelope[Data]) -> bytes:
        raise AssertionError("RAM planning does not serialize an envelope")

    def decode(self, encoded: bytes) -> PlanEnvelope[Data]:
        raise AssertionError("RAM planning does not deserialize an envelope")

    def retained_bytes(self, value: PlanEnvelope[Data]) -> int:
        return retained_entry_bytes(value)


def contract(name="test.base", *, declarations=()):
    metadata = PlanContractMetadata(id=name, schema_version=1, algorithm_version=1)

    def fingerprint(world_uid, scope, inputs, dependencies):
        return input_fingerprint(metadata, world_uid, scope, inputs, dependencies, MANIFEST)

    return RegisteredPlanContract(metadata, TypeAdapter(Data).validate_python, fingerprint,
        declarations, CacheBinding(CacheContract[PlanEnvelope[Data]](id="cache." + name, schema_version=1),
                                  EnvelopeCodec()), MANIFEST)


def request(binding, value=2, *, world="world", scope=None, deps=()):
    inputs = Data(value=value)
    scope = WorldPlanScope() if scope is None else scope
    metadata = binding.metadata
    return PlanRequest[Data](key=PlanKey(world_uid=world, scope=scope, contract_id=metadata.id,
        schema_version=metadata.schema_version, algorithm_version=metadata.algorithm_version,
        input_fingerprint=binding.fingerprint_inputs(world, scope, inputs, deps)),
        inputs=inputs, dependencies=deps)


class Wait:
    def __init__(self, seconds=None):
        self.cancelled = Event()
        self.deadline = None if seconds is None else monotonic() + seconds

    def raise_if_cancelled(self):
        if self.cancelled.is_set():
            raise PlanWaitCancelled()

    def remaining_seconds(self):
        return None if self.deadline is None else self.deadline - monotonic()


class Provider:
    def __init__(self, fn=None):
        self.count = 0
        self.fn = fn
        self.lock = Lock()

    def build(self, request, dependencies, control):
        with self.lock:
            self.count += 1
        if self.fn:
            return self.fn(request, dependencies, control)
        return PlanBuildResult[Data](payload=Data(value=request.inputs.value * 2), diagnostics=())


class Harness:
    def __init__(self, *, policy=None, cache_policy=None):
        self.registry = PlanRegistry()
        self.policy = cache_policy or CachePolicy(max_retained_bytes=1000000, max_entry_bytes=500000)
        self.backend = MemoryCache(self.policy)
        self.cache = CacheService(self.backend, self.policy)
        self.service = PlanningService(self.registry, self.cache,
            policy or PlanningExecutionPolicy(max_workers=2, max_pending_builds=4))
        self.empty = PlanDependencyReader(self.registry)

    def register(self, binding=None, provider=None):
        binding, provider = binding or contract(), provider or Provider()
        self.registry.register(binding, provider)
        return binding, provider

    def get(self, binding, *, value=2, dependencies=None, wait=None, req=None):
        return self.service.get_or_build(binding, req or request(binding, value),
            dependencies or self.empty, wait=wait or Wait(5))


class CanonicalTests(unittest.TestCase):
    def test_exact_primitive_tlv_vectors_and_no_bool_int_collision(self):
        def tlv(tag, payload):
            return bytes([tag]) + len(payload).to_bytes(8, "big") + payload
        for value, expected in ((None, tlv(0, b"")), (True, tlv(1, b"\x01")),
                                (0, tlv(2, b"\x00\x00")), (-256, tlv(2, b"\x01\x01\x00")),
                                ("я", tlv(4, "я".encode())), (b"x", tlv(5, b"x"))):
            self.assertEqual(CANONICAL.encode(value), expected)
        self.assertNotEqual(CANONICAL.encode(True), CANONICAL.encode(1))
        self.assertEqual(CANONICAL.encode(-0.0), CANONICAL.encode(0.0))

    def test_sets_sorted_sequences_ordered_and_manifest_ids_stable(self):
        self.assertEqual(CANONICAL.encode(frozenset((3, 1))), CANONICAL.encode(frozenset((1, 3))))
        self.assertNotEqual(CANONICAL.encode((3, 1)), CANONICAL.encode((1, 3)))
        model = Data(value=1)
        self.assertEqual(CANONICAL.encode(model), CanonicalCodec(CANONICAL.manifest).encode(model))
        renamed = CanonicalCodec(CanonicalSchemaManifest(entries=tuple(item.model_copy(update={"type_id": 99})
            if item.python_type is Data else item for item in MANIFEST.entries)))
        self.assertNotEqual(CANONICAL.encode(model), renamed.encode(model))

    def test_unknown_types_mutability_nonfinite_and_incomplete_records_rejected(self):
        @dataclass(frozen=True)
        class Unknown:
            value: int
        for invalid in ([], {}, set(), float("inf"), float("nan"), Unknown(1),
                        Data.model_construct(), Data(value=1).model_copy(update={"extra": 1})):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                CANONICAL.encode(invalid)
        with self.assertRaises(ValueError):
            CanonicalSchemaManifest(entries=(RegisteredTypeEntry(type_id=1, python_type=Data, kind=CanonicalTypeKind.RECORD),
                RegisteredTypeEntry(type_id=1, python_type=PlanKey, kind=CanonicalTypeKind.RECORD)))

    def test_enum_tag_is_distinct_from_wire_string(self):
        self.assertNotEqual(CANONICAL.encode(WorldPlanScope().kind), CANONICAL.encode("world"))


if __name__ == "__main__":
    unittest.main()
