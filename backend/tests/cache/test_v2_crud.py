from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase
from unittest.mock import patch

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry
from app.application.cache.service.cacheService import CacheFailure, CacheService
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission
from app.dataModel.cache.contracts.cacheError import CacheFailureReason, CacheIssueCode, CacheOperation
from app.dataModel.cache.contracts.cacheEvictResult import CacheEvictOutcome
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheMiss
from app.dataModel.cache.contracts.cacheUpdateResult import CacheUpdateOutcome
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from tests.cache.test_memory_backend import BytesCodec, entry


class CrudTests(TestCase):
    def setUp(self):
        self.a, self.b, self.c = (entry(i) for i in range(3))
        self.codec = BytesCodec()
        self.backend = MemoryCache(CachePolicy(max_entry_bytes=16000, max_retained_bytes=32000))
        registry = CacheBindingRegistry((CacheBinding(self.a.key.contract, self.codec),))
        self.cache = CacheService(self.backend, registry)

    def race(self, operation, left, right):
        barrier = Barrier(2)

        def run(value):
            barrier.wait(timeout=5)
            try:
                return operation(value).outcome
            except CacheFailure as failure:
                return failure.error

        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(run, (left, right)))

    def test_atomic_create_and_evict(self):
        self.assertCountEqual(self.race(self.cache.create, self.a, self.a),
                              [CacheAdmission.STORED, CacheAdmission.ALREADY_PRESENT])
        self.assertGreater(self.backend.retained_bytes, 0)
        self.assertEqual(self.cache.get(self.a.key).entry.value, self.a.value)
        self.assertCountEqual(self.race(self.cache.evict, self.a.key, self.a.key),
                              [CacheEvictOutcome.EVICTED, CacheEvictOutcome.NOT_FOUND])
        self.assertEqual(self.backend.retained_bytes, 0)
        self.assertIsInstance(self.cache.get(self.a.key), CacheMiss)

    def test_competing_values_and_update(self):
        other = entry(value=b"other")
        self.assertEqual(self.cache.update(other).outcome, CacheUpdateOutcome.NOT_FOUND)
        left, right = self.race(self.cache.create, self.a, other)
        if left == CacheAdmission.STORED:
            winner, loser, error = self.a, other, right
        else:
            self.assertEqual(right, CacheAdmission.STORED)
            winner, loser, error = other, self.a, left
        self.assertEqual(error.operation, CacheOperation.CREATE)
        self.assertEqual(error.issues[0].code, CacheIssueCode.KEY_OCCUPIED_DIFFERENT_VALUE)
        with self.assertRaises(CacheFailure) as caught:
            self.cache.update(loser)
        self.assertEqual(caught.exception.error.operation, CacheOperation.UPDATE)
        self.assertEqual(self.cache.get(winner.key).entry.value, winner.value)

    def test_lru_and_size_priority(self):
        for operation, refresh in ((self.cache.create, False), (self.cache.update, False), (None, True)):
            with self.subTest(operation=operation):
                for item in (self.a, self.b, self.c):
                    self.cache.evict(item.key)
                with patch.object(self.codec, "retained_bytes", return_value=16000):
                    self.cache.create(self.a)
                    self.cache.create(self.b)
                    if operation:
                        operation(self.a)
                    else:
                        self.cache.get(self.a.key)
                    self.cache.create(self.c)
                self.assertIsInstance(self.cache.get(self.b.key if refresh else self.a.key), CacheMiss)
        with patch.object(self.codec, "retained_bytes", return_value=16001):
            self.assertEqual(self.cache.create(self.a).outcome, CacheAdmission.ALREADY_PRESENT)
            self.assertEqual(self.cache.create(self.b).outcome, CacheAdmission.SKIPPED_OVERSIZE)
        self.assertEqual(self.backend.retained_bytes, 32000)

    def test_failed_encoding_leaves_entry_intact(self):
        self.cache.create(self.a)
        with patch.object(self.codec, "encode", side_effect=ValueError("bad payload")):
            with self.assertRaises(CacheFailure) as caught:
                self.cache.update(self.a)
        self.assertEqual(caught.exception.error.reason, CacheFailureReason.INVALID_PAYLOAD)
        self.assertEqual(self.cache.update(self.a).outcome, CacheUpdateOutcome.UNCHANGED)

    def test_lookup_failures_do_not_become_misses(self):
        with patch.object(self.backend, "get", side_effect=OSError("private cause")) as get:
            for key, code in ((entry(version=2).key, CacheIssueCode.SCHEMA_VERSION_MISMATCH),
                              (entry(namespace="domain.other").key, CacheIssueCode.UNKNOWN_NAMESPACE)):
                with self.assertRaises(CacheFailure) as caught:
                    self.cache.get(key)
                self.assertEqual(caught.exception.error.issues[0].code, code)
            get.assert_not_called()
            with self.assertRaises(CacheFailure) as caught:
                self.cache.get(self.a.key)
            self.assertEqual(caught.exception.error.reason, CacheFailureReason.BACKEND_FAILURE)
            self.assertEqual(caught.exception.error.issues, ())
            self.assertIsInstance(caught.exception.__cause__, OSError)

    def test_hit_with_wrong_key_or_invalid_payload(self):
        invalid = self.a.model_copy(update={"value": 123})
        for returned, reason in ((self.b, CacheFailureReason.CONTRACT_MISMATCH),
                                 (invalid, CacheFailureReason.INVALID_PAYLOAD)):
            with patch.object(self.backend, "get", return_value=CacheHit.model_construct(entry=returned)):
                with self.assertRaises(CacheFailure) as caught:
                    self.cache.get(self.a.key)
                self.assertEqual(caught.exception.error.reason, reason)

    def test_write_backend_failure_keeps_operation_identity(self):
        for name, argument in (("create", self.a), ("update", self.a), ("evict", self.a.key)):
            with patch.object(self.backend, name, side_effect=OSError("private cause")):
                with self.assertRaises(CacheFailure) as caught:
                    getattr(self.cache, name)(argument)
                self.assertEqual(caught.exception.error.reason, CacheFailureReason.BACKEND_FAILURE)
                self.assertEqual(caught.exception.error.operation, CacheOperation(name))
                self.assertEqual(caught.exception.error.issues, ())
