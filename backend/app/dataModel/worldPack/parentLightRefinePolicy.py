"""L0→L2 refine knobs — WP-PERF-22 Parent light refine contracts."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class ParentLightRefinePolicy(BaseModel):
    """Upsample / z-band / noise — single SoT for L2 refine generators."""

    SCHEMA_ID: ClassVar[str] = "SCH-PARENT-LIGHT-REFINE-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    z_band: int = Field(default=1, ge=0)
    resample: Literal["bilinear", "nearest"] = "bilinear"
    # Detail noise amplitude around resampled L0 form (then clamped by z_band).
    detail_noise_amplitude: int = Field(default=1, ge=0)
    # Categorical L0 system_terrain → meter; bilinear forbidden (mask carry).
    terrain_resample: Literal["nearest"] = "nearest"

    @classmethod
    def canonical_defaults(cls) -> ParentLightRefinePolicy:
        return cls()
