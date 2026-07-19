"""Declared world extent AABB — grid / macro-tile index space.

Wire: ``world.world_bounds`` JSON ``{x_min,x_max,y_min,y_max}``.
See docs/tz_terrain_generation.md § Охват мира / Форма мира.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class WorldBounds(BaseModel):
    """Axis-aligned world extent (inclusive). Square = special case W==H."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-BOUNDS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    x_min: int
    x_max: int
    y_min: int
    y_max: int

    @model_validator(mode="after")
    def _ordered(self) -> WorldBounds:
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError("world_bounds requires x_min<=x_max and y_min<=y_max")
        return self

    @classmethod
    def try_parse(cls, raw: object) -> WorldBounds | None:
        """Parse DB/JSON blob; invalid or incomplete → None."""
        if not isinstance(raw, dict):
            return None
        try:
            return cls.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            return None
