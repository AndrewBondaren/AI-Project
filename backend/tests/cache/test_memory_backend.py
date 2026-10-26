"""PC-3: bounded LRU, shared partitions, concurrent access and restart."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from sys import getsizeof
import unittest

from pydantic import TypeAdapter

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBackend, CacheBinding
from app.application.cache.service.cacheService import CacheService, retained_entry_bytes
from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy


def entry(index=0, *, namespace="domain.alpha", version=1, value=b"payload"):
    contract = CacheContract[bytes](id=namespace, schema_version=version)
    key = CacheKey[bytes](contract=contract, item_key=index.to_bytes(32, "big"))
    return CacheEntry[bytes](key=key, value=value)


class BytesCodec:
    def validate(self, value: object) -> bytes:
        return TypeAdapter(bytes).validate_python(value, strict=True)

    def encode(self, value: bytes) -> bytes:
        return value

    def decode(self, encoded: bytes) -> bytes:
        return encoded

    def retained_bytes(self, value: bytes) -> int:
        return retained_entry_bytes(value)


class MemoryCacheTests(unittest.TestCase):
    def test_lru_hit_refreshes_order_and_domains_share_one_budget(self):
        entries = (entry(0), entry(1, namespace="domain.bravo"), entry(2, version=2))
        costs = [retained_entry_bytes(item) for item in entries]
        policy = CachePolicy(max_retained_bytes=sum(costs[:2]), max_entry_bytes=max(costs))
        backend = MemoryCache(policy)
        for item in entries[:2]:
            backend.put(item)
        self.assertIsInstance(backend.get(entries[0].key), CacheHit)
        backend.put(entries[2])
        self.assertIsInstance(backend.get(entries[1].key), CacheMiss)
        self.assertEqual(backend.get(entries[0].key).entry.value, entries[0].value)
        self.assertEqual(backend.get(entries[2].key).entry.value, entries[2].value)
        self.assertLessEqual(backend.retained_bytes, policy.max_retained_bytes)

    def test_replacement_and_eviction_release_cost(self):
        small, large = entry(), entry(value=b"longer" * 1000)
        budget = retained_entry_bytes(large)
        backend = MemoryCache(CachePolicy(max_retained_bytes=budget, max_entry_bytes=budget))
        backend.put(small)
        backend.put(large)
        self.assertEqual(backend.retained_bytes, budget)
        self.assertEqual(backend.get(small.key).entry.value, large.value)
        backend.put(small)
        self.assertEqual(backend.retained_bytes, retained_entry_bytes(small))
        backend.evict(small.key)
        backend.evict(small.key)
        self.assertEqual(backend.retained_bytes, 0)

    def test_clear_restart_and_immutable_values_preserve_authoritative_inputs(self):
        item = entry(value=b"authored data")
        policy = CachePolicy(max_retained_bytes=100000, max_entry_bytes=50000)
        backend = MemoryCache(policy)
        service = CacheService(backend, policy)
        binding = CacheBinding(item.key.contract, BytesCodec())
        self.assertEqual(service.put(binding, item), CacheAdmission.STORED)
        warm = service.get(binding, item.key).entry.value
        self.assertIs(warm, item.value)
        with self.assertRaises(TypeError):
            warm[0] = 1
        backend.clear()
        self.assertEqual(backend.retained_bytes, 0)
        for cold in (backend, MemoryCache(policy)):
            replay = CacheService(cold, policy)
            self.assertIsInstance(replay.get(binding, item.key), CacheMiss)
            replay.put(binding, item)
            self.assertEqual(replay.get(binding, item.key).entry.value, warm)
        self.assertEqual(item.value, b"authored data")

    def test_oversized_result_skips_admission_without_evicting_existing(self):
        small = entry()
        budget = retained_entry_bytes(small) + 1000
        policy = CachePolicy(max_retained_bytes=budget, max_entry_bytes=budget)
        backend = MemoryCache(policy)
        service = CacheService(backend, policy)
        binding = CacheBinding(small.key.contract, BytesCodec())
        service.put(binding, small)
        large = entry(1, value=bytes(budget * 2))
        self.assertEqual(service.put(binding, large), CacheAdmission.SKIPPED_OVERSIZE)
        self.assertEqual(service.get(binding, small.key).entry.value, small.value)
        self.assertIsInstance(service.get(binding, large.key), CacheMiss)
        with self.assertRaises(ValueError):
            backend.put(large)
        self.assertLessEqual(backend.retained_bytes, budget)

    def test_parallel_put_get_evict_clear_stays_bounded(self):
        policy = CachePolicy(max_retained_bytes=20000, max_entry_bytes=10000)
        backend = MemoryCache(policy)

        def run(index):
            item = entry(index)
            for _ in range(10):
                backend.put(item)
                result = backend.get(item.key)
                if isinstance(result, CacheHit):
                    self.assertEqual(result.entry.value, item.value)
                backend.evict(item.key)
                if index % 7 == 0:
                    backend.clear()
                self.assertLessEqual(backend.retained_bytes, policy.max_retained_bytes)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(run, range(32)))
        backend.clear()
        self.assertEqual(backend.retained_bytes, 0)

    def test_graph_accounting_counts_shared_children_once_and_slots(self):
        shared = b"same object" * 100
        pair = (shared, shared)
        self.assertEqual(retained_entry_bytes(pair), getsizeof(pair) + getsizeof(shared))

        @dataclass(frozen=True, slots=True)
        class Box:
            child: bytes

        box = Box(shared)
        self.assertEqual(retained_entry_bytes(box), getsizeof(box) + getsizeof(shared))
        self.assertGreater(retained_entry_bytes(entry(value=shared)), getsizeof(shared))

    def test_one_backend_handles_distinct_payload_types_with_nested_immutability(self):
        from tests.cache.test_service import Codec, Mode, Payload, Point

        policy = CachePolicy(max_retained_bytes=100000, max_entry_bytes=50000)
        service = CacheService(MemoryCache(policy), policy)
        raw = entry()
        raw_binding = CacheBinding(raw.key.contract, BytesCodec())
        model_binding = CacheBinding(CacheContract[Payload](id="domain.model", schema_version=1), Codec())
        model_key = CacheKey[Payload](contract=model_binding.contract, item_key=raw.key.item_key)
        payload = Payload(points=(Point(1),), limit=10, mode=Mode.NORMAL)
        service.put(raw_binding, raw)
        service.put(model_binding, CacheEntry[Payload](key=model_key, value=payload))
        self.assertEqual(service.get(raw_binding, raw.key).entry.value, raw.value)
        retrieved = service.get(model_binding, model_key).entry.value
        self.assertEqual(retrieved, payload)
        with self.assertRaises(AttributeError):
            retrieved.points[0].x = 9
        self.assertEqual(service.get(model_binding, model_key).entry.value.points[0].x, 1)


def protocol_acceptance(backend: MemoryCache) -> CacheBackend:
    return backend


if __name__ == "__main__":
    unittest.main()
