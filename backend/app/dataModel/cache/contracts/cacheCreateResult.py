from pydantic import BaseModel, ConfigDict

from app.dataModel.cache.contracts.cacheEntry import CacheAdmission


class CacheCreateResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    outcome: CacheAdmission
