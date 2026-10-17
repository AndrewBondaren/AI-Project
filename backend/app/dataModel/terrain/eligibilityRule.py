"""Coverage scorer input data — tz_map_light_bake § Реестр и CoverageResolver."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EligibilityRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact: str = Field(min_length=1)
    op: Literal["gte", "lte", "in_range", "flag"]
    lo: float | None = Field(default=None, allow_inf_nan=False)
    hi: float | None = Field(default=None, allow_inf_nan=False)
    weight: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    required: bool = False

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        if self.op in ("gte", "in_range") and self.lo is None:
            raise ValueError(f"{self.op} requires lo")
        if self.op in ("lte", "in_range") and self.hi is None:
            raise ValueError(f"{self.op} requires hi")
        if self.lo is not None and self.hi is not None and self.lo > self.hi:
            raise ValueError("eligibility requires lo <= hi")
        return self
