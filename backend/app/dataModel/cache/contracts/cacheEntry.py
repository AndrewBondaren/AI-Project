"""A typed retained value; retention decisions do not change that value."""

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.cache.identity.cacheKey import CacheKey


T = TypeVar("T")


class CacheAdmission(StrEnum):
    STORED = "stored"
    SKIPPED_OVERSIZE = "skipped_oversize"


class CacheEntry(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: CacheKey[T]
    value: T
