"""A hit always has an entry; a miss never carries a nullable payload."""

from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.cache.contracts.cacheEntry import CacheEntry


T = TypeVar("T")


class CacheLookupStatus(StrEnum):
    HIT = "hit"
    MISS = "miss"


class CacheHit(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    status: Literal[CacheLookupStatus.HIT] = CacheLookupStatus.HIT
    entry: CacheEntry[T]


class CacheMiss(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    status: Literal[CacheLookupStatus.MISS] = CacheLookupStatus.MISS


type CacheLookup[T] = Annotated[CacheHit[T] | CacheMiss, Field(discriminator="status")]
