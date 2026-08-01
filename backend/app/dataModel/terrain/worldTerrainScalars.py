"""Terrain generation scalars on `worlds` row (not registries).

Wire projection / startup column sync: thin wrappers over
``app.dataModel.worldScalarWire`` (**JV-SCALARS-1**).
Consumers: ``terrain_scalars(world)`` via ``jsonValidation.worldRow``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.worldScalarWire import (
    pojo_wire_keys,
    scalar_wire_from_mapping,
    validate_world_row_pojo_columns,
)

CHUNK_COLUMNS_MIN = 1
SUBSURFACE_DEPTH_MIN = 0


class WorldTerrainScalars(BaseModel):
    """Scalar terrain/map fields on `worlds` — tz_json_validation.md world row."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-TERRAIN-SCALARS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    terrain_chunk_columns: DefaultOnWire[int] = constrained_field(
        default=32, greater_equals=CHUNK_COLUMNS_MIN,
    )
    terrain_parallel_workers: DefaultOnWire[int | None] = None
    map_subsurface_depth: DefaultOnWire[int] = constrained_field(
        default=0, greater_equals=SUBSURFACE_DEPTH_MIN,
    )
    z_min: DefaultOnWire[int | None] = None
    z_max: DefaultOnWire[int | None] = None
    # NULL в БД → POJO None (не материализовано); fallback в resolved_* / canonical_defaults.
    # constrained_field(greater_equals=…) здесь ломает terrain_scalars(): resolve кладёт явный None,
    # Pydantic падает на bound. Плюс: отрицательные значения не режутся на model_validate — долг;
    # при необходимости — import strict (GV-3) или проверка в resolved_*.
    elevation_lapse_rate: DefaultOnWire[float | None] = None
    g: DefaultOnWire[float] = constrained_field(default=1.0, greater=0.0)
    closed_planet_grid: DefaultOnWire[bool] = False
    magma_band_thickness: DefaultOnWire[int | None] = None  # см. elevation_lapse_rate

    @classmethod
    def canonical_defaults(cls) -> WorldTerrainScalars:
        """Explicit scalars after normalize."""
        return cls(z_min=-500, z_max=8000, elevation_lapse_rate=0.65)

    @classmethod
    def resolved_z_min(cls, z_min: int | None) -> int:
        if z_min is not None:
            return int(z_min)
        default = cls.canonical_defaults().z_min
        return int(default) if default is not None else -500

    @classmethod
    def resolved_z_max(cls, z_max: int | None) -> int:
        if z_max is not None:
            return int(z_max)
        default = cls.canonical_defaults().z_max
        return int(default) if default is not None else 8000

    @classmethod
    def resolved_elevation_lapse_rate(cls, lapse: float | None) -> float:
        if lapse is not None:
            return float(lapse)
        default = cls.canonical_defaults().elevation_lapse_rate
        return float(default) if default is not None else 0.65


TERRAIN_SCALAR_WIRE_KEYS: frozenset[str] = pojo_wire_keys(WorldTerrainScalars)


def terrain_scalar_wire_from_mapping(source: Any) -> dict[str, Any]:
    """Project ``worlds`` row or wire dict → wire slice for ``resolve_model``."""
    return scalar_wire_from_mapping(TERRAIN_SCALAR_WIRE_KEYS, source)


def validate_world_row_terrain_columns(world_cls: type) -> None:
    """Startup assert: every POJO scalar field has a matching ``World`` column."""
    validate_world_row_pojo_columns(world_cls, WorldTerrainScalars, label="terrain")
