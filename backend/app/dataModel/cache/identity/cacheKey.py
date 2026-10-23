"""Typed cache namespace and opaque lookup digest."""

from typing import Generic, NewType, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.cache.contracts.cacheContract import CacheContract


CacheItemKey = NewType("CacheItemKey", bytes)
T = TypeVar("T")


class CacheKey(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    contract: CacheContract[T]
    item_key: CacheItemKey = Field(strict=True, min_length=32, max_length=32)
