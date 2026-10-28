"""Canonical plate parameters; effective tiny-world count is computed by the producer."""

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt


class PlateGenerationPolicy(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always", validate_default=True)

    plate_count: StrictInt = Field(default=12, gt=0)
    blend_length_fraction: StrictFloat = Field(default=0.12, gt=0, allow_inf_nan=False)
