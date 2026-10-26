"""L0→L2 refine knobs — WP-PERF-22 Parent light refine contracts."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParentLightRefinePolicy(BaseModel):
    """Upsample / z-band / noise — single SoT for L2 refine generators."""

    SCHEMA_ID: ClassVar[str] = "SCH-PARENT-LIGHT-REFINE-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    z_band: int = Field(default=1, ge=0)
    resample: Literal["bilinear", "nearest"] = "bilinear"
    # Detail noise amplitude around resampled L0 form (then clamped by z_band).
    detail_noise_amplitude: int = Field(default=1, ge=0)
    # Categorical L0 attrs (terrain / facing / grade_uid) → fine cell; bilinear forbidden.
    categorical_resample: Literal["nearest"] = "nearest"

    @model_validator(mode="before")
    @classmethod
    def _reject_terrain_resample(cls, data: object) -> object:
        """Removed wire key ``terrain_resample`` reads as an error (PAR-T-2)."""
        if isinstance(data, dict) and "terrain_resample" in data:
            raise ValueError("terrain_resample was removed; use categorical_resample")
        return data

    @classmethod
    def canonical_defaults(cls) -> ParentLightRefinePolicy:
        return cls()
