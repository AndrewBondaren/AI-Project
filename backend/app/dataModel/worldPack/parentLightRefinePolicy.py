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
    # Categorical L0 attrs (terrain / facing / grade_uid) → meter; bilinear forbidden.
    categorical_resample: Literal["nearest"] = "nearest"

    @model_validator(mode="before")
    @classmethod
    def _migrate_terrain_resample_alias(cls, data: object) -> object:
        """Legacy wire key ``terrain_resample`` → ``categorical_resample`` (PAR-T-2)."""
        if not isinstance(data, dict):
            return data
        if "categorical_resample" in data:
            return data
        legacy = data.get("terrain_resample")
        if legacy is not None:
            migrated = dict(data)
            migrated["categorical_resample"] = legacy
            migrated.pop("terrain_resample", None)
            return migrated
        return data

    @property
    def terrain_resample(self) -> Literal["nearest"]:
        """Deprecated alias — use ``categorical_resample`` (PAR-T-2)."""
        return self.categorical_resample

    @classmethod
    def canonical_defaults(cls) -> ParentLightRefinePolicy:
        return cls()
