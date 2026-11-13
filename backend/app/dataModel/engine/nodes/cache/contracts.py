"""Cache lookup composition and declared domain error transport."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.dataModel.cache.contracts.cacheCreateResult import CacheCreateResult
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheError import CacheError
from app.dataModel.cache.contracts.cacheEvictResult import CacheEvictResult
from app.dataModel.cache.contracts.cacheLookup import CacheLookup
from app.dataModel.cache.contracts.cacheUpdateResult import CacheUpdateResult
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.engine.dag.errors.nodeError import NodeError


class ReadCacheEntryInput[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    key: CacheKey[T]


class ReadCacheEntryOutput[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    key: CacheKey[T]
    lookup: CacheLookup[T]


class CacheNodeError(NodeError):
    error: CacheError


class CreateCacheEntryInput[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    kind: Literal["create"]
    request: CacheEntry[T]


class CreateCacheEntryOutput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    kind: Literal["create"]
    value: CacheCreateResult


class UpdateCacheEntryInput[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    kind: Literal["update"]
    request: CacheEntry[T]


class UpdateCacheEntryOutput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    kind: Literal["update"]
    value: CacheUpdateResult


class EvictCacheEntryInput[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    kind: Literal["evict"]
    request: CacheKey[T]


class EvictCacheEntryOutput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    kind: Literal["evict"]
    value: CacheEvictResult
