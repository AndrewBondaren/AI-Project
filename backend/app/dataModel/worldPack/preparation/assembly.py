"""Metadata shared by unfinished Pack composition and the stored manifest."""

from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.core.constants import FINE_CELL_SIZE
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.worldPack.bake.packBakeMode import PackBakeMode
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.dataModel.worldPack.meta.worldGridSettings import WorldGridSettings
from app.dataModel.worldPack.meta.worldPackManifest import (
    ChunkRefineRole, SettlementStructureStatus, WildernessRefineStatus,
)
from app.dataModel.worldPack.preparation.nestedAdmission import strict_metadata_record
from app.dataModel.worldPack.wire.climateFieldWire import ClimateBakeStatus
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.wire.worldMapCellsPerTile import resolve_world_map_side


def _volume(value: object) -> TerritoryVolume:
    return strict_metadata_record(TerritoryVolume, value)


def _region(value: object) -> WildernessRegionEntry:
    return strict_metadata_record(WildernessRegionEntry, value)


_GRID_SCALE = bind_field(FieldRef(lambda: WorldGridSettings, lambda value: value.fine_cells_per_map_cell))
_CHUNK_COLUMNS = bind_field(FieldRef(lambda: WorldTerrainScalars, lambda value: value.terrain_chunk_columns))
_SUBSURFACE = bind_field(FieldRef(lambda: WorldTerrainScalars, lambda value: value.map_subsurface_depth))
_GRID_ADAPTER = TypeAdapter(WorldGridSettings.model_fields[_GRID_SCALE.field].rebuild_annotation())
_CHUNK_ADAPTER = TypeAdapter(WorldTerrainScalars.model_fields[_CHUNK_COLUMNS.field].rebuild_annotation())
_SUBSURFACE_ADAPTER = TypeAdapter(WorldTerrainScalars.model_fields[_SUBSURFACE.field].rebuild_annotation())


class _PackAssemblyValue(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    @model_validator(mode="after")
    def immutable_value(self) -> Self:
        validate_immutable(self)
        return self


class PackChunkAssembly(_PackAssemblyValue):
    cx: int = Field(ge=0)
    cy: int = Field(ge=0)
    refine_role: ChunkRefineRole | None


class PackTileAssembly(_PackAssemblyValue):
    gx: int
    gy: int
    climate_status: ClimateBakeStatus
    wilderness_refine_status: WildernessRefineStatus
    chunks: tuple[PackChunkAssembly, ...]


class PackLocationAssembly(_PackAssemblyValue):
    location_uid: EntityUid
    territory_volume: Annotated[TerritoryVolume, BeforeValidator(_volume)]
    climate_status: ClimateBakeStatus


class PackSettlementAssembly(_PackAssemblyValue):
    location_uid: EntityUid
    territory_volume: Annotated[TerritoryVolume, BeforeValidator(_volume)]
    structure_status: SettlementStructureStatus
    packed_district_uids: tuple[EntityUid, ...]


class PackAssemblyInput(_PackAssemblyValue):
    last_l0_mode: PackBakeMode
    fine_cells_per_map_cell: int
    world_map_cells_per_tile: int
    fine_cell_size: int
    map_subsurface_depth: int
    terrain_chunk_columns: int
    tiles: tuple[PackTileAssembly, ...]
    locations: tuple[PackLocationAssembly, ...]
    settlements: tuple[PackSettlementAssembly, ...]
    wilderness_regions: tuple[Annotated[WildernessRegionEntry, BeforeValidator(_region)], ...]

    @field_validator("fine_cells_per_map_cell")
    @classmethod
    def grid_scale(cls, value: int) -> int:
        _GRID_ADAPTER.validate_python(value, strict=True)
        return value

    @field_validator("terrain_chunk_columns")
    @classmethod
    def chunk_columns(cls, value: int) -> int:
        _CHUNK_ADAPTER.validate_python(value, strict=True)
        return value

    @field_validator("map_subsurface_depth")
    @classmethod
    def subsurface(cls, value: int) -> int:
        _SUBSURFACE_ADAPTER.validate_python(value, strict=True)
        return value

    @field_validator("world_map_cells_per_tile")
    @classmethod
    def effective_side(cls, value: int) -> int:
        if resolve_world_map_side(value) != value:
            raise ValueError("expected resolved world map side")
        return value

    @field_validator("fine_cell_size")
    @classmethod
    def fine_grid_unit(cls, value: int) -> int:
        if value != FINE_CELL_SIZE:
            raise ValueError("fine cell size differs from the grid unit")
        return value
