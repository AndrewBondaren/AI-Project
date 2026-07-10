"""Climate field blob wire — tier A coarse + optional tier B."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator


class ClimateSampleWire(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    temperature_base: int | None = None
    rainfall: int | None = None


class ClimateFieldWire(BaseModel):
    """Rectangular climate grid sampled in pack."""

    SCHEMA_ID: ClassVar[str] = "SCH-CLIMATE-FIELD-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    tier: str = "A"
    origin_x: int = 0
    origin_y: int = 0
    width: int
    height: int
    samples: list[ClimateSampleWire]

    @field_validator("tier")
    @classmethod
    def _tier(cls, value: str) -> str:
        norm = str(value).strip().upper()
        if norm not in {"A", "B"}:
            raise ValueError("tier must be A or B")
        return norm

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
        lx = x - self.origin_x
        ly = y - self.origin_y
        if lx < 0 or ly < 0 or lx >= self.width or ly >= self.height:
            return None
        idx = ly * self.width + lx
        return self.samples[idx]
