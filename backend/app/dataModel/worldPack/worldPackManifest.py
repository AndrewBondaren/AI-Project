"""World Pack manifest.json wire — docs/tz_world_pack_storage.md § manifest."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.worldPack.climateFieldWire import ClimateBakeStatusMixin
from app.dataModel.worldPack.mapCellSize import MAP_CELL_SIZE_M_DEFAULT
from app.dataModel.worldPack.packBakeDefaults import PACK_CODEC_VERSION
from app.dataModel.worldPack.packBakeMode import PackBakeMode
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldMapCellsPerTile import WORLD_MAP_CELLS_PER_TILE

PACK_WIRE_VERSION = "1.0.0"
BakeMode = PackBakeMode  # manifest last L0 mode — not "detailed"
WildernessRefineStatus = Literal["absent", "partial", "complete"]
ChunkRefineRole = Literal["scene", "background", "path", "location"]


class ChunkRef(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    cx: int
    cy: int
    refine_role: ChunkRefineRole | None = None
    content_hash: str | None = None
    bytes: int | None = None


class TileManifestEntry(ClimateBakeStatusMixin):
    gx: int
    gy: int
    world_map_path: str | None = None
    world_map_hash: str | None = None
    wilderness_refine_status: WildernessRefineStatus = "absent"
    chunks: list[ChunkRef] = Field(default_factory=list)


class SettlementStructureEntry(BaseModel):
    """Manifest row for `locations/l.{uid}.settlement.zst` — not location_terrain."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: str
    territory_volume: TerritoryVolume
    structure_path: str | None = None
    structure_hash: str | None = None
    bytes: int | None = None


class LocationTerrainEntry(ClimateBakeStatusMixin):
    location_uid: str
    territory_volume: TerritoryVolume
    terrain_path: str | None = None
    terrain_hash: str | None = None
    z_band: str | None = None
    bytes: int | None = None


class WorldPackManifest(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-PACK-MANIFEST"

    model_config = ConfigDict(extra="ignore")

    pack_version: str = PACK_WIRE_VERSION
    world_uid: str
    content_hash: str | None = None
    codec_version: int = PACK_CODEC_VERSION
    payload_format: str = "json"
    registry_hash: str | None = None
    bake_mode: BakeMode = "light"
    map_cell_size_m: int = MAP_CELL_SIZE_M_DEFAULT
    world_map_cells_per_tile: int = WORLD_MAP_CELLS_PER_TILE
    cell_size_m: int = 1
    map_subsurface_depth: int = 0
    location_terrain_entries: list[LocationTerrainEntry] = Field(default_factory=list)
    settlement_structure_entries: list[SettlementStructureEntry] = Field(default_factory=list)
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

    def settlement_structure_entry(self, location_uid: str) -> SettlementStructureEntry | None:
        for loc in self.settlement_structure_entries:
            if loc.location_uid == location_uid:
                return loc
        return None
