"""Authored L0 override; resolved side/default remains owned by its existing policy."""

from typing import Annotated, Any, ClassVar
from pydantic import BaseModel, BeforeValidator, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.worldPack.worldMapCellsPerTile import coerce_world_map_override
from app.dataModel.worldScalarWire import pojo_wire_keys, scalar_wire_from_mapping, validate_world_row_pojo_columns


class WorldMapResolutionSettings(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-MAP-RESOLUTION-SETTINGS"
    model_config = ConfigDict(extra="ignore", frozen=True)

    world_map_cells_per_tile: DefaultWhenMissing[
        Annotated[int | None, BeforeValidator(coerce_world_map_override)]
    ] = None

    @classmethod
    def canonical_defaults(cls) -> "WorldMapResolutionSettings":
        return cls()


MAP_RESOLUTION_WIRE_KEYS = pojo_wire_keys(WorldMapResolutionSettings)


def map_resolution_wire_from_mapping(source: Any) -> dict[str, Any]:
    return scalar_wire_from_mapping(MAP_RESOLUTION_WIRE_KEYS, source)


def validate_world_row_map_resolution_columns(world_cls: type) -> None:
    validate_world_row_pojo_columns(world_cls, WorldMapResolutionSettings, label="map resolution")
