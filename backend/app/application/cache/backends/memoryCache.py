"""One bounded, thread-safe RAM LRU shared across typed namespaces."""

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

from app.application.cache.service.cacheService import retained_entry_bytes
from app.dataModel.cache.contracts.cacheContract import CacheContractId, CacheSchemaVersion
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
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


class MemoryCache:
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
            while self._retained_bytes + cost > self._policy.max_retained_bytes:
                _, oldest = self._entries.popitem(last=False)
                self._retained_bytes -= oldest.cost
            self._entries[address] = _Retained(entry.value, cost)
            self._retained_bytes += cost

    def evict[T](self, key: CacheKey[T]) -> None:
        with self._lock:
            previous = self._entries.pop(_address(key), None)
            if previous is not None:
                self._retained_bytes -= previous.cost

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._retained_bytes = 0
