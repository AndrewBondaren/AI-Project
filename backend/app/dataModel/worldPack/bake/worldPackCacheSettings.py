from pydantic import BaseModel, ConfigDict, PositiveInt

from app.dataModel.cache.policy.cachePolicy import CachePolicy


class WorldPackCacheSettings(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    manifest_cache: CachePolicy
    manifest_max_bytes: PositiveInt | None = None
