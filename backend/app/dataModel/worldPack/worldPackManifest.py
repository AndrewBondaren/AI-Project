"""World Pack manifest.json wire — docs/tz_world_pack_storage.md § manifest."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataModel.worldPack.climateFieldWire import (
    ClimateBakeStatus,
    normalize_climate_bake_status,
)
from app.dataModel.worldPack.territoryVolume import TerritoryVolume

PACK_WIRE_VERSION = "1.0.0"
BakeMode = Literal["light", "full"]
WildernessRefineStatus = Literal["absent", "partial", "complete"]
ChunkRefineRole = Literal["scene", "background", "path"]


class ChunkRef(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    cx: int
    cy: int
    refine_role: ChunkRefineRole | None = None
    content_hash: str | None = None
    bytes: int | None = None


class TileManifestEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    gx: int
    gy: int
    world_map_path: str | None = None
    world_map_hash: str | None = None
    wilderness_refine_status: WildernessRefineStatus = "absent"
    climate_status: ClimateBakeStatus = "coarse"
    chunks: list[ChunkRef] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _legacy_climate_tier(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "climate_status" not in data and "climate_tier" in data:
            data = {**data, "climate_status": data["climate_tier"]}
        return data

    @field_validator("climate_status", mode="before")
    @classmethod
    def _climate_status(cls, value: Any) -> ClimateBakeStatus:
        return normalize_climate_bake_status(value)


class LocationTerrainEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: str
    territory_volume: TerritoryVolume
    terrain_path: str | None = None
    terrain_hash: str | None = None
    climate_status: ClimateBakeStatus = "coarse"
    z_band: str | None = None
    bytes: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_climate_tier(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "climate_status" not in data and "climate_tier" in data:
            data = {**data, "climate_status": data["climate_tier"]}
        return data

    @field_validator("climate_status", mode="before")
    @classmethod
    def _climate_status(cls, value: Any) -> ClimateBakeStatus:
        return normalize_climate_bake_status(value)


class WorldPackManifest(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-PACK-MANIFEST"

    model_config = ConfigDict(extra="ignore")

    pack_version: str = PACK_WIRE_VERSION
    world_uid: str
    content_hash: str | None = None
    codec_version: int = 1
    payload_format: str = "json"
    registry_hash: str | None = None
    bake_mode: BakeMode = "light"
    map_cell_size_m: int = 3000
    world_map_cells_per_tile: int = 32
    cell_size_m: int = 1
    map_subsurface_depth: int = 0
    location_terrain_entries: list[LocationTerrainEntry] = Field(default_factory=list)
    tiles: list[TileManifestEntry] = Field(default_factory=list)
    world_map_cells: int = 0
    wilderness_tiles_total: int = 0
    wilderness_chunks_baked: int = 0

    def tile_entry(self, gx: int, gy: int) -> TileManifestEntry | None:
        for tile in self.tiles:
            if tile.gx == gx and tile.gy == gy:
                return tile
        return None

    def chunk_ref(self, gx: int, gy: int, cx: int, cy: int) -> ChunkRef | None:
        tile = self.tile_entry(gx, gy)
        if tile is None:
            return None
        for chunk in tile.chunks:
            if chunk.cx == cx and chunk.cy == cy:
                return chunk
        return None

    def location_entry(self, location_uid: str) -> LocationTerrainEntry | None:
        for loc in self.location_terrain_entries:
            if loc.location_uid == location_uid:
                return loc
        return None
