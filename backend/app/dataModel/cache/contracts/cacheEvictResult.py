from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class CacheEvictOutcome(StrEnum):
    EVICTED = "evicted"
    NOT_FOUND = "not_found"


class CacheEvictResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    outcome: CacheEvictOutcome
