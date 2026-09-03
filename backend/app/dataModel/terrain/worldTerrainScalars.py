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
# Persist chunk side — not L0 ``WORLD_MAP_CELLS_PER_TILE`` (POJO-D-5).
TERRAIN_CHUNK_COLUMNS_DEFAULT = 32
CANONICAL_Z_MIN = -500
CANONICAL_Z_MAX = 8000
CANONICAL_ELEVATION_LAPSE_RATE = 0.65


class WorldTerrainScalars(BaseModel):
    """Scalar terrain/map fields on `worlds` — tz_json_validation.md world row."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-TERRAIN-SCALARS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    terrain_chunk_columns: DefaultOnWire[int] = constrained_field(
        default=TERRAIN_CHUNK_COLUMNS_DEFAULT, greater_equals=CHUNK_COLUMNS_MIN,
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
        return cls(
            z_min=CANONICAL_Z_MIN,
            z_max=CANONICAL_Z_MAX,
            elevation_lapse_rate=CANONICAL_ELEVATION_LAPSE_RATE,
        )

    @classmethod
    def resolved_z_min(cls, z_min: int | None) -> int:
        if z_min is not None:
            return int(z_min)
        default = cls.canonical_defaults().z_min
        if default is None:
            raise RuntimeError("WorldTerrainScalars.canonical_defaults().z_min is None")
        return int(default)

    @classmethod
    def resolved_z_max(cls, z_max: int | None) -> int:
        if z_max is not None:
            return int(z_max)
        default = cls.canonical_defaults().z_max
        if default is None:
            raise RuntimeError("WorldTerrainScalars.canonical_defaults().z_max is None")
        return int(default)

    @classmethod
    def resolved_elevation_lapse_rate(cls, lapse: float | None) -> float:
        if lapse is not None:
            return float(lapse)
        default = cls.canonical_defaults().elevation_lapse_rate
        if default is None:
            raise RuntimeError(
                "WorldTerrainScalars.canonical_defaults().elevation_lapse_rate is None",
            )
        return float(default)


TERRAIN_SCALAR_WIRE_KEYS: frozenset[str] = pojo_wire_keys(WorldTerrainScalars)


def terrain_scalar_wire_from_mapping(source: Any) -> dict[str, Any]:
    """Project ``worlds`` row or wire dict → wire slice for ``resolve_model``."""
    return scalar_wire_from_mapping(TERRAIN_SCALAR_WIRE_KEYS, source)


def validate_world_row_terrain_columns(world_cls: type) -> None:
    """Startup assert: every POJO scalar field has a matching ``World`` column."""
    validate_world_row_pojo_columns(world_cls, WorldTerrainScalars, label="terrain")
