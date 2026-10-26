"""Synchronous storage protocol; codecs own concrete payload schemas."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
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


class CacheBackend(Protocol):
    """Store immutable entries under exact keys; failures must raise."""

    def get[T](self, key: CacheKey[T]) -> CacheLookup[T]: ...
    def put[T](self, entry: CacheEntry[T]) -> None: ...
    def evict[T](self, key: CacheKey[T]) -> None: ...
