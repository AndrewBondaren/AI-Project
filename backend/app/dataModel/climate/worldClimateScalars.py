"""Climate policy scalars on `worlds` row (not registries).

Two layers (not duplicate hardcodes in generators):

- ``Field(default=…)`` — normalize-on-import when JSON key is missing.
- ``canonical_defaults()`` — full ``fixtures/world_template.json`` climate block
  (peak band -40/45, season offsets, explicit pole fields).

Wire keys ``climate_pole_mode`` / ``climate_pole_preset`` must match
``ClimatePoleMode`` / ``ClimatePolePreset`` enums. ``default_climate_zone``
must match ``ClimateZone.TEMPERATE``. Consumers: ``climate_scalars(world)``
via ``jsonValidation.worldRow``, not raw literals in generators/DAG/db. См. ``docs/tz_json_validation.md``.

Wire projection: ``CLIMATE_SCALAR_WIRE_KEYS`` + ``climate_scalar_wire_from_mapping``.
Startup sync: ``validate_world_row_climate_columns(World)`` — POJO fields ⊆ ``worlds`` columns.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire
from app.dataModel.constrainedField import constrained_field

# Sync with ClimatePoleMode / ClimatePolePreset / ClimateZone.TEMPERATE (no enum import — package cycle).
DEFAULT_CLIMATE_ZONE = "temperate"
DEFAULT_CLIMATE_POLE_MODE = "autoresolve"
DEFAULT_CLIMATE_POLE_PRESET = "binary"
DEFAULT_PRECIPITATION_LIQUID = "water"
DEFAULT_LOCAL_INFLUENCE_FRACTION = 0.1

# Fixture peak band — only in canonical_defaults / world_template (Field default None).
CANONICAL_PEAK_TEMP_MIN = -40
CANONICAL_PEAK_TEMP_MAX = 45


class SeasonTempOffsets(BaseModel):
    """`worlds.season_temp_offsets` — ENUM-E E-21 keys."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    winter: OptionalOnWire[int] = 0
    spring: OptionalOnWire[int] = 0
    summer: OptionalOnWire[int] = 0
    autumn: OptionalOnWire[int] = 0

    @classmethod
    def canonical_fixture(cls) -> SeasonTempOffsets:
        """fixtures/world_template.json ``season_temp_offsets``."""
        return cls(winter=-12, spring=0, summer=8, autumn=-4)


class WorldClimateScalars(BaseModel):
    """Scalar climate fields on `worlds` — tz_climate.md, tz_json_validation.md."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-CLIMATE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    default_climate_zone: OptionalOnWire[str] = DEFAULT_CLIMATE_ZONE
    climate_temperature_peak_min: OptionalOnWire[int | None] = None
    climate_temperature_peak_max: OptionalOnWire[int | None] = None
    climate_pole_mode: OptionalOnWire[str] = DEFAULT_CLIMATE_POLE_MODE
    climate_pole_preset: OptionalOnWire[str] = DEFAULT_CLIMATE_POLE_PRESET
    climate_local_influence_fraction: OptionalOnWire[float] = constrained_field(
        default=DEFAULT_LOCAL_INFLUENCE_FRACTION,
        greater_equals=0.0,
        lesser_equals=1.0,
    )
    precipitation_liquid: OptionalOnWire[str] = DEFAULT_PRECIPITATION_LIQUID
    season_temp_offsets: OptionalOnWire[SeasonTempOffsets] = Field(default_factory=SeasonTempOffsets)

    @classmethod
    def canonical_defaults(cls) -> WorldClimateScalars:
        """fixtures/world_template.json climate block."""
        return cls(
            default_climate_zone=DEFAULT_CLIMATE_ZONE,
            climate_temperature_peak_min=CANONICAL_PEAK_TEMP_MIN,
            climate_temperature_peak_max=CANONICAL_PEAK_TEMP_MAX,
            climate_pole_mode=DEFAULT_CLIMATE_POLE_MODE,
            climate_pole_preset=DEFAULT_CLIMATE_POLE_PRESET,
            climate_local_influence_fraction=DEFAULT_LOCAL_INFLUENCE_FRACTION,
            precipitation_liquid=DEFAULT_PRECIPITATION_LIQUID,
            season_temp_offsets=SeasonTempOffsets.canonical_fixture(),
        )

    @classmethod
    def resolve_peak_bounds(
        cls,
        peak_min: int | None,
        peak_max: int | None,
    ) -> tuple[int, int]:
        """Peak band from world row with canonical fallback."""
        defaults = cls.canonical_defaults()
        lo = peak_min if peak_min is not None else defaults.climate_temperature_peak_min
        hi = peak_max if peak_max is not None else defaults.climate_temperature_peak_max
        assert lo is not None and hi is not None
        if lo > hi:
            lo, hi = hi, lo
        return int(lo), int(hi)


CLIMATE_SCALAR_WIRE_KEYS: frozenset[str] = frozenset(WorldClimateScalars.model_fields.keys())


def climate_scalar_wire_from_mapping(source: Any) -> dict[str, Any]:
    """Project ``worlds`` row or wire dict → wire slice for ``resolve_model``."""
    if isinstance(source, dict):
        return {key: source.get(key) for key in CLIMATE_SCALAR_WIRE_KEYS}
    return {key: getattr(source, key, None) for key in CLIMATE_SCALAR_WIRE_KEYS}


def validate_world_row_climate_columns(world_cls: type) -> None:
    """Startup assert: every POJO scalar field has a matching ``World`` column."""
    row_fields = {field.name for field in dataclass_fields(world_cls)}
    missing = CLIMATE_SCALAR_WIRE_KEYS - row_fields
    if missing:
        raise RuntimeError(
            f"{world_cls.__name__} missing climate scalar columns "
            f"{sorted(missing)} — sync with WorldClimateScalars",
        )
