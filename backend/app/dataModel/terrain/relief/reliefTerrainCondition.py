"""One terrain condition with three slope policies — tz_terrain_relief R26/R32."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import StrictEnumOnWire, StrictOnWire
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain, ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefRoleCase import ReliefRoleCase


_REQUIRED_POLICIES = frozenset({
    ReliefSlopePolicy.SLOPE_DOWN,
    ReliefSlopePolicy.SLOPE_UP,
    ReliefSlopePolicy.SLOPE_NONE,
})


class ReliefTerrainCondition(BaseModel):
    """Exactly three cases (down/up/none); whole condition Mode A XOR Mode B."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    terrain: StrictEnumOnWire[ReliefConditionTerrain]
    cases: StrictOnWire[list[ReliefRoleCase]] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _policies_and_mode(self) -> ReliefTerrainCondition:
        policies = [c.policy for c in self.cases]
        if len(set(policies)) != 3 or set(policies) != _REQUIRED_POLICIES:
            raise ValueError(
                "cases must be exactly slope_down, slope_up, slope_none (unique)"
            )
        modes = {c.is_mode_a for c in self.cases}
        if len(modes) != 1:
            raise ValueError("all cases in one condition must share Mode A or Mode B")
        return self

    @property
    def is_mode_a(self) -> bool:
        return self.cases[0].is_mode_a

    def case_for(self, policy: ReliefSlopePolicy) -> ReliefRoleCase:
        for case in self.cases:
            if case.policy == policy:
                return case
        raise KeyError(policy)
