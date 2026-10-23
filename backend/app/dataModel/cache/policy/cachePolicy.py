"""Explicit retention limits, LRU eviction and disabled TTL."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class CacheEvictionPolicy(StrEnum):
    LRU = "lru"


class CachePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    max_retained_bytes: StrictInt = Field(gt=0)
    max_entry_bytes: StrictInt = Field(gt=0)
    eviction: CacheEvictionPolicy = CacheEvictionPolicy.LRU
    ttl_seconds: None = None

    @model_validator(mode="after")
    def entry_fits_budget(self) -> Self:
        if self.max_entry_bytes > self.max_retained_bytes:
            raise ValueError("max_entry_bytes exceeds max_retained_bytes")
        return self
