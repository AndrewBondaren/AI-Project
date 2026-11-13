import base64
import json
import unittest

from pydantic import BaseModel, ConfigDict, ValidationError

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.contracts.manifestBytesCodec import ManifestBytesCodec
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry
from app.application.cache.service.cacheService import CacheService
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.worldPack.meta.manifestCacheContract import MANIFEST_BYTES_CONTRACT


class BinaryRequest(BaseModel):
    """Test-only composition: the engine does not own nested byte encoding."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    entry: CacheEntry[bytes]


class BinaryResponse(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    lookup: CacheLookup[bytes]


class CacheBinaryTransportTests(unittest.TestCase):
    def key(self, raw=bytes([255]) * 32):
        return CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT, item_key=raw)

    def test_keys_and_payloads_round_trip_without_utf8_assumptions(self):
        for raw_key in (bytes(32), bytes([255]) * 32, bytes(range(224, 256))):
            for value in (b"", b"plain text", b"\x00\xff\x80", bytes(range(256))):
                with self.subTest(key=raw_key, value=value):
                    key = self.key(raw_key)
                    entry = CacheEntry[bytes](key=key, value=value)
                    wire = entry.model_dump_json(round_trip=True)
                    decoded = json.loads(wire)
                    self.assertEqual(decoded["key"]["item_key"], base64.urlsafe_b64encode(raw_key).decode())
                    self.assertEqual(decoded["value"], base64.urlsafe_b64encode(value).decode())
                    restored = CacheEntry[bytes].model_validate_json(wire)
                    self.assertEqual(restored, entry)
                    self.assertEqual(restored.key.item_key, raw_key)
                    self.assertEqual(restored.value, value)
                    self.assertIs(type(restored.value), bytes)
                    self.assertEqual(entry.model_dump()["value"], value)
                    self.assertEqual(CacheKey[bytes].model_validate_json(key.model_dump_json()), key)

    def test_invocation_transport_preserves_cache_identity_and_hit(self):
        cache = CacheService(
            MemoryCache(CachePolicy(max_entry_bytes=16000, max_retained_bytes=32000)),
            CacheBindingRegistry((CacheBinding(MANIFEST_BYTES_CONTRACT, ManifestBytesCodec()),)),
        )
        request = BinaryRequest(entry=CacheEntry[bytes](key=self.key(), value=bytes(range(256))))
        wire = InvocationCoordinator.encode(request, BinaryRequest)
        restored = BinaryRequest.model_validate_json(wire)
        self.assertEqual(cache.create(restored.entry).outcome, CacheAdmission.STORED)
        # Look up using the original binary key, not the deserialized object.
        response = BinaryResponse(lookup=cache.get(request.entry.key))
        self.assertIsInstance(response.lookup, CacheHit)
        output_wire = InvocationCoordinator.encode(response, BinaryResponse)
        output = BinaryResponse.model_validate_json(output_wire)
        self.assertEqual(output, response)
        self.assertEqual(output.lookup.entry.value, request.entry.value)
        cache.evict(request.entry.key)
        missing = BinaryResponse(lookup=cache.get(request.entry.key))
        missing_wire = InvocationCoordinator.encode(missing, BinaryResponse)
        self.assertIsInstance(BinaryResponse.model_validate_json(missing_wire).lookup, CacheMiss)

    def test_invalid_binary_fields_report_both_errors(self):
        wire = CacheEntry[bytes](key=self.key(), value=b"valid").model_dump(mode="json")
        wire["key"]["item_key"] = "!"
        wire["value"] = "!"
        with self.assertRaises(ValidationError) as raised:
            CacheEntry[bytes].model_validate_json(json.dumps(wire))
        self.assertEqual([e["loc"] for e in raised.exception.errors()], [("key", "item_key"), ("value",)])

    def test_decoded_key_length_and_python_strictness_are_preserved(self):
        wire = self.key().model_dump(mode="json")
        for length in (31, 33):
            wire["item_key"] = base64.urlsafe_b64encode(bytes(length)).decode()
            with self.subTest(length=length), self.assertRaises(ValidationError):
                CacheKey[bytes].model_validate_json(json.dumps(wire))
        with self.assertRaises(ValidationError):
            CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT, item_key="x" * 32)
        with self.assertRaises(ValidationError):
            CacheEntry[bytes](key=self.key(), value="base64 is only JSON transport")

    def test_non_bytes_values_keep_their_existing_wire_shape(self):
        entry = CacheEntry[int](key=CacheKey[int](contract=MANIFEST_BYTES_CONTRACT, item_key=bytes(32)), value=42)
        self.assertEqual(json.loads(entry.model_dump_json())["value"], 42)
        self.assertEqual(CacheEntry[int].model_validate_json(entry.model_dump_json()), entry)
