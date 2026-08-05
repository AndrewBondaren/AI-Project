"""``relief_pick_policy.canal_obstacle_policy`` rules — tz_terrain_relief R36p."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.terrain.relief.enums import CanalObstacleEntity


class CanalObstaclePolicyRule(BaseModel):
    """One clearance-path canal rule: enable cut for listed entities."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    to_canal_cut_enable: StrictOnWire[bool]
    entities: StrictOnWire[list[CanalObstacleEntity]] = Field(min_length=1)
    canal_ref: DefaultOnWire[str | None] = None

    @model_validator(mode="after")
    def _ref_only_when_enable(self) -> CanalObstaclePolicyRule:
        if not self.to_canal_cut_enable and self.canal_ref:
            raise ValueError(
                "canal_ref only allowed when to_canal_cut_enable=true (R36p)"
            )
        if not self.entities:
            raise ValueError("canal_obstacle_policy.entities must be non-empty")
        return self
