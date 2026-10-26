"""Resolved surface scale inputs; values come from the owning settings resolver."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class SurfaceGridSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    fine_span: StrictInt = Field(gt=0)
    light_side: StrictInt = Field(gt=0)
