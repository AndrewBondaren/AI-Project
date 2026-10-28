"""Shared field quantization settings; independent of field generation recipes."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class WaterFieldSelectionPolicy(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always", validate_default=True)

    score_bits: StrictInt = Field(default=24, ge=8, le=30)
