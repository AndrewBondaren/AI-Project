"""World-fine length fraction and normalized fBm parameters (GEO-1 §6.29-F)."""

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt


class ContinentalNoisePolicy(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always", validate_default=True)

    length_fraction: StrictFloat = Field(default=0.18, gt=0, allow_inf_nan=False)
    octaves: StrictInt = Field(default=4, ge=1, le=16)
    lacunarity: StrictFloat = Field(default=2.0, gt=1, allow_inf_nan=False)
    persistence: StrictFloat = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
