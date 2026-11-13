"""A typed retained value; retention decisions do not change that value."""

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.cache.identity.cacheKey import CacheKey


T = TypeVar("T")


class CacheAdmission(StrEnum):
    STORED = "stored"
    ALREADY_PRESENT = "already_present"
    SKIPPED_OVERSIZE = "skipped_oversize"


class CacheEntry(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always",
                              ser_json_bytes="base64", val_json_bytes="base64")

    key: CacheKey[T]
    value: T
