"""One bounded, thread-safe RAM LRU shared across typed namespaces."""

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import cast

from app.application.cache.contracts.cacheBackend import CachePayloadCodec, CacheEncodingFailure, CacheValueConflict
from app.dataModel.cache.contracts.cacheEvictResult import CacheEvictOutcome
from app.dataModel.cache.contracts.cacheUpdateResult import CacheUpdateOutcome

from app.application.cache.service.cacheService import retained_entry_bytes
from app.dataModel.cache.contracts.cacheContract import CacheContractId, CacheSchemaVersion
from app.dataModel.cache.contracts.cacheEntry import CacheEntry, CacheAdmission
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheItemKey, CacheKey
from app.dataModel.cache.policy.cachePolicy import CachePolicy


type _Address = tuple[CacheContractId, CacheSchemaVersion, CacheItemKey]


@dataclass(frozen=True)
class _Retained:
    value: object
    cost: int


def _address[T](key: CacheKey[T]) -> _Address:
    return key.contract.id, key.contract.schema_version, key.item_key


class _MemoryStore:
    """Store values admitted by CacheService; never infer world freshness.

    The heterogeneous private storage erases payload types to object. Reads
    reconstruct the caller's typed entry; CacheService validates its concrete
    binding before delivery. No consumer cast or domain import is needed.
    """

    def __init__(self, policy: CachePolicy):
        self._policy = CachePolicy.model_validate(policy)
        self._entries: OrderedDict[_Address, _Retained] = OrderedDict()
        self._retained_bytes = 0
        self._lock = RLock()

    @property
    def retained_bytes(self) -> int:
        with self._lock:
            return self._retained_bytes

    def get[T](self, key: CacheKey[T]) -> CacheLookup[T]:
        address = _address(key)
        with self._lock:
            retained = self._entries.get(address)
            if retained is None:
                return CacheMiss()
            self._entries.move_to_end(address)
            entry = CacheEntry[T].model_validate({"key": key, "value": retained.value})
            return CacheHit[T](entry=entry)

    def _insert(self, address: _Address, value: object, cost: int) -> None:
        while self._retained_bytes + cost > self._policy.max_retained_bytes:
            _, oldest = self._entries.popitem(last=False)
            self._retained_bytes -= oldest.cost
        self._entries[address] = _Retained(value, cost)
        self._retained_bytes += cost

    def _remove(self, address: _Address) -> CacheEvictOutcome:
        with self._lock:
            previous = self._entries.pop(address, None)
            if previous is None:
                return CacheEvictOutcome.NOT_FOUND
            self._retained_bytes -= previous.cost
            return CacheEvictOutcome.EVICTED


class MemoryCache(_MemoryStore):
    def _matches[T](self, stored: _Retained, entry: CacheEntry[T], codec: CachePayloadCodec[T]) -> None:
        # Address includes namespace/version. Both values were admitted by the same binding.
        try:
            existing = codec.encode(cast(T, stored.value))
            incoming = codec.encode(entry.value)
            if type(existing) is not bytes or type(incoming) is not bytes:
                raise ValueError("canonical codec must return bytes")
        except Exception as exc:
            raise CacheEncodingFailure("invalid canonical payload") from exc
        if existing != incoming:
            raise CacheValueConflict("occupied key has a different value")

    def create[T](self, entry: CacheEntry[T], codec: CachePayloadCodec[T], cost: int) -> CacheAdmission:
        if type(cost) is not int or cost < 0:
            raise ValueError("invalid retention cost")
        address = _address(entry.key)
        with self._lock:
            stored = self._entries.get(address)
            if stored is not None:
                self._matches(stored, entry, codec)
                return CacheAdmission.ALREADY_PRESENT
            if cost > self._policy.max_entry_bytes:
                return CacheAdmission.SKIPPED_OVERSIZE
            self._insert(address, entry.value, cost)
            return CacheAdmission.STORED

    def update[T](self, entry: CacheEntry[T], codec: CachePayloadCodec[T]) -> CacheUpdateOutcome:
        with self._lock:
            stored = self._entries.get(_address(entry.key))
            if stored is None:
                return CacheUpdateOutcome.NOT_FOUND
            self._matches(stored, entry, codec)
            return CacheUpdateOutcome.UNCHANGED

    def evict[T](self, key: CacheKey[T]) -> CacheEvictOutcome:
        return self._remove(_address(key))


class LegacyMemoryCache(_MemoryStore):
    """LEGACY REMOVE(CACHE-V1-BINDING): replaceable V1 records until caller cutover."""

    def put[T](self, entry: CacheEntry[T]) -> None:
        cost = retained_entry_bytes(entry)
        if cost > self._policy.max_entry_bytes:
            # Service performs this check before calling a backend. Direct misuse
            # is an error, not successful storage of a silently dropped value.
            raise ValueError("entry exceeds memory cache admission limit")
        address = _address(entry.key)
        with self._lock:
            previous = self._entries.pop(address, None)
            if previous is not None:
                self._retained_bytes -= previous.cost
            self._insert(address, entry.value, cost)

    def evict[T](self, key: CacheKey[T]) -> None:
        self._remove(_address(key))

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._retained_bytes = 0
