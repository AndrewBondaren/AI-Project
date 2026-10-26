"""Required process resource policies; absent configuration never means unlimited."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy


class PlanningRuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    cache: CachePolicy
    execution: PlanningExecutionPolicy
