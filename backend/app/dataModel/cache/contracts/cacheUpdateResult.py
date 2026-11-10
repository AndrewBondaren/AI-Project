from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class CacheUpdateOutcome(StrEnum):
    NOT_FOUND = "not_found"
    UNCHANGED = "unchanged"


class CacheUpdateResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    outcome: CacheUpdateOutcome
