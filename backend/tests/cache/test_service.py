"""PC-2 contract, corruption and backend substitution acceptance."""

from dataclasses import dataclass
from enum import StrEnum
import unittest
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic.dataclasses import dataclass as validated_dataclass

from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.service.cacheService import CacheFailure, CacheFailureReason, CacheService
from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy


class Mode(StrEnum):
    NORMAL = "normal"


@validated_dataclass(frozen=True, config=ConfigDict(strict=True, extra="forbid", revalidate_instances="always"))
class Point:
    x: int


class Payload(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    points: tuple[Point, ...]
    limit: int = Field(gt=0)
    mode: Mode

    @model_validator(mode="after")
    def unique_bounded_points(self):
        xs = tuple(point.x for point in self.points)
        if len(set(xs)) != len(xs) or any(x >= self.limit for x in xs):
            raise ValueError("duplicate or out-of-bounds point")
        return self


class Codec:
    def __init__(self):
        self.cost = 20

    def validate(self, value: object) -> Payload:
        return TypeAdapter(Payload).validate_python(value, strict=True)

    def encode(self, value: Payload) -> bytes:
        raise AssertionError("RAM service does not serialize values")

    def decode(self, encoded: bytes) -> Payload:
        raise AssertionError("RAM service does not deserialize values")

    def retained_bytes(self, value: Payload) -> int:
        return self.cost


class BackendDouble:
    def __init__(self):
        self.entries = {}
        self.error = None
        self.lookup = None
        self.calls = []

    def check(self, method):
        self.calls.append(method)
        if self.error:
            raise self.error

    def get(self, key):
        self.check("get")
        if self.lookup is not None:
            return self.lookup
        return CacheHit(entry=self.entries[key]) if key in self.entries else CacheMiss()

    def put(self, entry):
        self.check("put")
        self.entries[entry.key] = entry

    def evict(self, key):
        self.check("evict")
        self.entries.pop(key, None)


class CacheServiceTests(unittest.TestCase):
    def setUp(self):
        self.backend = BackendDouble()
        self.codec = Codec()
        self.binding = CacheBinding(CacheContract[Payload](id="test.payload", schema_version=1), self.codec)
        self.key = CacheKey[Payload](contract=self.binding.contract, item_key=bytes(32))
        self.payload = Payload(points=(Point(1),), limit=10, mode=Mode.NORMAL)
        self.entry = CacheEntry[Payload](key=self.key, value=self.payload)
        self.service = CacheService(self.backend, CachePolicy(max_retained_bytes=100, max_entry_bytes=50))

    def fails(self, reason, action):
        with self.assertRaises(CacheFailure) as caught:
            action()
        self.assertEqual(caught.exception.reason, reason)
        self.assertTrue(caught.exception.issues)
        return caught.exception

    def test_backend_substitution_hit_miss_and_evict(self):
        for backend in (self.backend, BackendDouble()):
            service = CacheService(backend, CachePolicy(max_retained_bytes=100, max_entry_bytes=50))
            self.assertIsInstance(service.get(self.binding, self.key), CacheMiss)
            self.assertEqual(service.put(self.binding, self.entry), CacheAdmission.STORED)
            self.assertEqual(service.get(self.binding, self.key).entry.value, self.payload)
            service.evict(self.binding, self.key)
            self.assertIsInstance(service.get(self.binding, self.key), CacheMiss)

    def test_namespace_version_and_revision_isolation(self):
        self.service.put(self.binding, self.entry)
        for contract, digest in ((CacheContract[Payload](id="another", schema_version=1), bytes(32)),
                                 (CacheContract[Payload](id="test.payload", schema_version=2), bytes(32)),
                                 (self.binding.contract, bytes([1]) * 32)):
            binding = CacheBinding(contract, self.codec)
            key = CacheKey[Payload](contract=contract, item_key=digest)
            self.assertIsInstance(self.service.get(binding, key), CacheMiss)
        wrong = CacheKey[Payload](contract=contract, item_key=bytes(32))
        other = CacheBinding(CacheContract[Payload](id="other", schema_version=1), self.codec)
        self.backend.calls.clear()
        for action in (lambda: self.service.get(other, wrong),
                       lambda: self.service.put(other, self.entry), lambda: self.service.evict(other, wrong)):
            self.fails(CacheFailureReason.CONTRACT_MISMATCH, action)
        self.assertEqual(self.backend.calls, [])

    def test_backend_failure_is_not_miss_and_cause_is_preserved(self):
        self.backend.error = OSError("storage unavailable")
        for action in (lambda: self.service.get(self.binding, self.key),
                       lambda: self.service.put(self.binding, self.entry),
                       lambda: self.service.evict(self.binding, self.key)):
            failure = self.fails(CacheFailureReason.BACKEND_FAILURE, action)
            self.assertIs(failure.__cause__, self.backend.error)

    def test_backend_wrong_key_is_rejected(self):
        wrong = self.key.model_copy(update={"item_key": bytes([1]) * 32})
        self.backend.lookup = CacheHit[Payload](entry=CacheEntry[Payload](key=wrong, value=self.payload))
        self.fails(CacheFailureReason.CONTRACT_MISMATCH, lambda: self.service.get(self.binding, self.key))

    def test_forged_existing_instances_are_revalidated_on_put_and_hit(self):
        point = Point(1)
        object.__setattr__(point, "x", True)
        bad_values = (
            self.payload.model_copy(update={"limit": True}),
            self.payload.model_copy(update={"limit": 0}),
            self.payload.model_copy(update={"mode": "unknown"}),
            self.payload.model_copy(update={"points": (point,)}),
            self.payload.model_copy(update={"points": (Point(1), Point(1))}),
            self.payload.model_copy(update={"points": (Point(10),)}),
            self.payload.model_copy(update={"points": [Point(1)]}),
            self.payload.model_copy(update={"extra": 1}),
            Payload.model_construct(points=(), mode=Mode.NORMAL),
        )
        for value in bad_values:
            with self.subTest(value=value):
                forged = self.entry.model_copy(update={"value": value})
                self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.put(self.binding, forged))
                self.backend.lookup = CacheHit[Payload].model_construct(entry=forged)
                self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.get(self.binding, self.key))
        self.assertNotIn("put", self.backend.calls)

    def test_corrupt_lookup_or_key_never_becomes_miss(self):
        for lookup in (None, {}, CacheMiss.model_construct(status="hit"),
                       CacheMiss.model_construct(extra=1), CacheHit[Payload].model_construct(),
                       CacheMiss.model_construct()):
            # Missing default discriminator must be rejected, not restored.
            if isinstance(lookup, CacheMiss) and lookup.status == CacheMiss().status and not lookup.model_extra:
                del lookup.__dict__["status"]
            self.backend.lookup = lookup
            if lookup is None:
                # Explicit backend returning None, rather than this double's normal mode.
                self.backend.get = lambda key: None
            else:
                self.backend.get = lambda key, result=lookup: result
            self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.get(self.binding, self.key))
        for bad in (self.key.model_copy(update={"item_key": bytes(1)}),
                    self.key.model_copy(update={"contract": self.binding.contract.model_copy(update={"schema_version": True})})):
            self.fails(CacheFailureReason.CONTRACT_MISMATCH, lambda: self.service.evict(self.binding, bad))

    def test_oversize_skips_storage_without_changing_value(self):
        self.codec.cost = 51
        self.assertEqual(self.service.put(self.binding, self.entry), CacheAdmission.SKIPPED_OVERSIZE)
        self.assertEqual(self.entry.value, self.payload)
        self.assertEqual(self.backend.calls, [])
        self.codec.cost = 50
        self.assertEqual(self.service.put(self.binding, self.entry), CacheAdmission.STORED)
        for cost in (True, -1, 1.5):
            self.codec.cost = cost
            self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.put(self.binding, self.entry))

    def test_mutable_or_opaque_nested_state_is_rejected_even_with_permissive_codec(self):
        @dataclass(frozen=True)
        class Box:
            content: object

        @dataclass
        class Mutable:
            x: int

        with patch.object(self.codec, "validate", side_effect=lambda value: value):
            for value in (Box([]), Box({"key": 1}), Box(set()), Box(Mutable(1)),
                          Box(object()), Box(float("nan")), Box(float("inf"))):
                forged = self.entry.model_copy(update={"value": value})
                with self.subTest(value=value):
                    self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.put(self.binding, forged))
        self.assertEqual(self.backend.calls, [])

    def test_codec_failure_and_missing_entry_fields_are_technical_errors(self):
        with patch.object(self.codec, "validate", side_effect=ValueError("invalid codec input")):
            self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.put(self.binding, self.entry))
            self.backend.lookup = CacheHit[Payload](entry=self.entry)
            self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.get(self.binding, self.key))
        for entry in (CacheEntry[Payload].model_construct(), self.entry.model_copy(update={"extra": 1})):
            self.fails(CacheFailureReason.INVALID_PAYLOAD, lambda: self.service.put(self.binding, entry))


if __name__ == "__main__":
    unittest.main()
