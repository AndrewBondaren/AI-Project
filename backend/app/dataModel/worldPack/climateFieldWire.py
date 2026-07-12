"""Climate field blob wire — coarse pack field + optional per-tile fine field."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ClimateBakeStatus = Literal["coarse", "fine"]

_LEGACY_STATUS = {
    "a": "coarse",
    "coarse": "coarse",
    "b": "fine",
    "fine": "fine",
}


def normalize_climate_bake_status(value: Any) -> ClimateBakeStatus:
    key = str(value).strip().lower()
    status = _LEGACY_STATUS.get(key)
    if status is None:
        raise ValueError("climate_status must be coarse or fine")
    return status  # type: ignore[return-value]


class ClimateSampleWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    temperature_base: int | None = None
    rainfall: int | None = None


class ClimateFieldWire(BaseModel):
    """Rectangular climate grid sampled in pack.

    coarse: ``origin_*`` / sample coords are **macro grid** indices; ``sample_step_m=1``.
    fine: ``origin_*`` are **meters**; ``sample_step_m`` is light-cell stride within the tile.
    """

    SCHEMA_ID: ClassVar[str] = "SCH-CLIMATE-FIELD-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    climate_status: ClimateBakeStatus = "coarse"
    origin_x: int = 0
    origin_y: int = 0
    width: int
    height: int
    sample_step_m: int = Field(default=1, ge=1)
    samples: list[ClimateSampleWire]

    @model_validator(mode="before")
    @classmethod
    def _legacy_tier_key(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "climate_status" not in data and "tier" in data:
            data = {**data, "climate_status": data["tier"]}
        return data

    @field_validator("climate_status", mode="before")
    @classmethod
    def _climate_status(cls, value: Any) -> ClimateBakeStatus:
        return normalize_climate_bake_status(value)

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

    def sample_meters(self, xm: int, ym: int) -> ClimateSampleWire | None:
        if self.climate_status != "fine":
            raise ValueError("sample_meters requires climate_status=fine")
        return self.sample_at(xm, ym)
