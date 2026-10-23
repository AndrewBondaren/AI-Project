"""Required execution limits; no consumer-defined numeric fallback."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class PlanningExecutionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    max_workers: StrictInt = Field(gt=0)
    max_pending_builds: StrictInt = Field(gt=0)
