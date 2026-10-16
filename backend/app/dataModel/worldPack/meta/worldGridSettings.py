"""World macro-cell scale; L0 mask resolution is an independent policy."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.constrainedField import constrained_field
from app.dataModel.worldPack.mapCellSize import FINE_CELLS_PER_MAP_CELL_DEFAULT
from app.dataModel.worldScalarWire import (
    pojo_wire_keys,
    scalar_wire_from_mapping,
    validate_world_row_pojo_columns,
)


class WorldGridSettings(BaseModel):
    """Fine cells along one side of a coarse map cell (macro-tile)."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-GRID-SETTINGS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    fine_cells_per_map_cell: DefaultWhenMissing[int] = constrained_field(
        default=FINE_CELLS_PER_MAP_CELL_DEFAULT,
        strict=True, greater_equals=1000, multiple_of=1000,
    )

    @classmethod
    def canonical_defaults(cls) -> WorldGridSettings:
        return cls()


GRID_SETTINGS_WIRE_KEYS: frozenset[str] = pojo_wire_keys(WorldGridSettings)


def grid_settings_wire_from_mapping(source: Any) -> dict[str, Any]:
    return scalar_wire_from_mapping(GRID_SETTINGS_WIRE_KEYS, source)


def validate_world_row_grid_columns(world_cls: type) -> None:
    validate_world_row_pojo_columns(world_cls, WorldGridSettings, label="grid")
