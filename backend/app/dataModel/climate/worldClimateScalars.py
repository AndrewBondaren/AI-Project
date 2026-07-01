"""Climate policy scalars on `worlds` row (not registries)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire


class SeasonTempOffsets(BaseModel):
    """`worlds.season_temp_offsets` — ENUM-E E-21 keys."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    winter: OptionalOnWire[int] = 0
    spring: OptionalOnWire[int] = 0
    summer: OptionalOnWire[int] = 0
    autumn: OptionalOnWire[int] = 0


class WorldClimateScalars(BaseModel):
    """Scalar climate fields on `worlds` — tz_climate.md, tz_json_validation.md."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    default_climate_zone: OptionalOnWire[str] = "temperate"
    climate_temperature_peak_min: OptionalOnWire[int | None] = None
    climate_temperature_peak_max: OptionalOnWire[int | None] = None
    climate_pole_mode: OptionalOnWire[str] = "autoresolve"
    climate_pole_preset: OptionalOnWire[str] = "binary"
    climate_local_influence_fraction: OptionalOnWire[float] = Field(default=0.1, ge=0.0, le=1.0)
    precipitation_liquid: OptionalOnWire[str] = "water"
    season_temp_offsets: OptionalOnWire[SeasonTempOffsets] = Field(default_factory=SeasonTempOffsets)

    @classmethod
    def canonical_defaults(cls) -> WorldClimateScalars:
        """fixtures/world_template.json climate block."""
        return cls(
            default_climate_zone="temperate",
            climate_temperature_peak_min=-40,
            climate_temperature_peak_max=45,
            climate_pole_mode="autoresolve",
            climate_pole_preset="binary",
            climate_local_influence_fraction=0.1,
            precipitation_liquid="water",
            season_temp_offsets=SeasonTempOffsets(winter=-12, spring=0, summer=8, autumn=-4),
        )
