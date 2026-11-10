"""Synchronous storage protocol; codecs own concrete payload schemas."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheEvictResult import CacheEvictOutcome
from app.dataModel.cache.contracts.cacheUpdateResult import CacheUpdateOutcome
from app.dataModel.cache.contracts.cacheLookup import CacheLookup
from app.dataModel.cache.identity.cacheKey import CacheKey


T = TypeVar("T")


class CachePayloadCodec(Protocol[T]):
    """Validate actual fields recursively, including constructed/copied instances.

    Validation is strict, without missing-field defaults. Encoding/decoding use
    the binding's canonical schema; retained_bytes counts the object graph once
    per object identity within an entry. Values must be deeply immutable.
    """

    def validate(self, value: object) -> T: ...
    def encode(self, value: T) -> bytes: ...
    def decode(self, encoded: bytes) -> T: ...
    def retained_bytes(self, value: T) -> int: ...


@dataclass(frozen=True)
class CacheBinding(Generic[T]):
    contract: CacheContract[T]
    codec: CachePayloadCodec[T]


class LegacyCacheBackend(Protocol):
    """LEGACY REMOVE(CACHE-V1-BINDING): port used by V1 CacheService."""

    def get[T](self, key: CacheKey[T]) -> CacheLookup[T]: ...
    def put[T](self, entry: CacheEntry[T]) -> None: ...
    def evict[T](self, key: CacheKey[T]) -> None: ...


class CacheValueConflict(ValueError):
    """An occupied key contains a different validated value."""


class CacheEncodingFailure(ValueError):
    """A codec could not provide canonical bytes for comparison."""


class CacheBackend(Protocol):
    """Atomic V2 operations on one bounded RAM cache."""

    def get[T](self, key: CacheKey[T]) -> CacheLookup[T]: ...
    def create[T](self, entry: CacheEntry[T], codec: CachePayloadCodec[T], cost: int) -> CacheAdmission: ...
    def update[T](self, entry: CacheEntry[T], codec: CachePayloadCodec[T]) -> CacheUpdateOutcome: ...
    def evict[T](self, key: CacheKey[T]) -> CacheEvictOutcome: ...
