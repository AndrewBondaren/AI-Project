"""Climate field blob wire — coarse pack field + optional per-tile fine field."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ClimateBakeStatus = Literal["coarse", "fine"]


def normalize_climate_bake_status(value: Any) -> ClimateBakeStatus:
    key = str(value).strip().lower()
    if key not in ("coarse", "fine"):
        raise ValueError("climate_status must be coarse or fine")
    return key  # type: ignore[return-value]


def reject_legacy_climate_status(data: Any, *, legacy_key: str) -> Any:
    """The removed ``legacy_key`` reads as an explicit error, not a silent drop."""
    if isinstance(data, dict) and legacy_key in data:
        raise ValueError(f"{legacy_key} was removed; use climate_status")
    return data


class ClimateBakeStatusMixin(BaseModel):
    """Shared ``climate_status`` wire + removed-key strictness guard."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    _climate_status_legacy_key: ClassVar[str] = "climate_tier"

    climate_status: ClimateBakeStatus = "coarse"

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_climate_status(cls, data: Any) -> Any:
        return reject_legacy_climate_status(
            data, legacy_key=cls._climate_status_legacy_key,
        )

    @field_validator("climate_status", mode="before")
    @classmethod
    def _normalize_climate_status(cls, value: Any) -> ClimateBakeStatus:
        return normalize_climate_bake_status(value)


class ClimateSampleWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    temperature_base: int | None = None
    rainfall: int | None = None


class ClimateFieldWire(ClimateBakeStatusMixin):
    """Rectangular climate grid sampled in pack.

    coarse: ``origin_*`` / sample coords are **macro grid** indices; ``sample_step_m=1``.
    fine: ``origin_*`` are **fine cells**; ``sample_step_m`` is light-cell stride within the tile.
    """

    SCHEMA_ID: ClassVar[str] = "SCH-CLIMATE-FIELD-WIRE"

    _climate_status_legacy_key: ClassVar[str] = "tier"

    origin_x: int = 0
    origin_y: int = 0
    width: int
    height: int
    sample_step_m: int = Field(default=1, ge=1)
    samples: list[ClimateSampleWire]

    @field_validator("samples")
    @classmethod
    def _sample_count(cls, samples: list[ClimateSampleWire], info) -> list[ClimateSampleWire]:
        width = info.data.get("width", 0)
        height = info.data.get("height", 0)
        expected = int(width) * int(height)
        if expected and len(samples) != expected:
            raise ValueError(f"samples length {len(samples)} != width*height {expected}")
        return samples

    def sample_at(self, x: int, y: int) -> ClimateSampleWire | None:
        step = max(1, int(self.sample_step_m))
        lx = (x - self.origin_x) // step
        ly = (y - self.origin_y) // step
        if lx < 0 or ly < 0 or lx >= self.width or ly >= self.height:
            return None
        idx = ly * self.width + lx
        return self.samples[idx]

    def sample_macro(self, gx: int, gy: int) -> ClimateSampleWire | None:
        if self.climate_status != "coarse":
            raise ValueError("sample_macro requires climate_status=coarse")
        return self.sample_at(gx, gy)

    def sample_fine(self, x_fine: int, y_fine: int) -> ClimateSampleWire | None:
        if self.climate_status != "fine":
            raise ValueError("sample_fine requires climate_status=fine")
        return self.sample_at(x_fine, y_fine)
