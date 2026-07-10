"""Read World Pack blobs and manifest."""

from __future__ import annotations

from pathlib import Path

from app.application.worldData.pack.packBlobWire import (
    parse_climate_field_payload,
    parse_world_map_tile_payload,
    parse_fine_terrain_chunk_payload,
)
from app.application.worldData.pack.fineTerrainDecodeCache import FineTerrainDecodeCache
from app.application.worldData.pack.packManifestStore import PackManifestStore
from app.application.worldData.pack.tileCodec import (
    PAYLOAD_KIND_CLIMATE,
    PAYLOAD_KIND_WORLD_MAP,
    PAYLOAD_KIND_FINE_TERRAIN,
    TileCodec,
)
from app.application.worldData.pack.worldPackPaths import WorldPackPaths
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.worldPackManifest import WorldPackManifest


class WorldPackReader:
    def __init__(
        self,
        paths: WorldPackPaths,
        *,
        codec: TileCodec | None = None,
        store: PackManifestStore | None = None,
        fine_terrain_cache: FineTerrainDecodeCache | None = None,
    ) -> None:
        self._paths = paths
        self._codec = codec or TileCodec()
        self._store = store or PackManifestStore()
        self._fine_terrain_cache = fine_terrain_cache
        self._manifest: WorldPackManifest | None = None

    def load_manifest(self) -> WorldPackManifest:
        path = self._paths.manifest_path()
        if not path.is_file():
            raise FileNotFoundError(f"manifest not found: {path}")
        self._manifest = self._store.load(path)
        return self._manifest

    @property
    def manifest(self) -> WorldPackManifest:
        if self._manifest is None:
            return self.load_manifest()
        return self._manifest

    @property
    def paths(self) -> WorldPackPaths:
        return self._paths

    def has_pack(self) -> bool:
        return self._paths.manifest_path().is_file()

    def read_world_map_tile(self, gx: int, gy: int) -> tuple[int, list[WorldMapCellWire]]:
        path = self._paths.world_map_tile_path(gx, gy)
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_WORLD_MAP:
            raise ValueError(f"expected world_map blob at {path}")
        return parse_world_map_tile_payload(payload)

    def read_wilderness_chunk(self, gx: int, gy: int, cx: int, cy: int) -> FineTerrainChunkWire:
        if self._fine_terrain_cache is None:
            return self._load_wilderness_chunk(gx, gy, cx, cy)
        return self._fine_terrain_cache.get_wilderness_chunk(
            (gx, gy, cx, cy),
            lambda: self._load_wilderness_chunk(gx, gy, cx, cy),
        )

    def read_location_terrain(self, location_uid: str) -> FineTerrainChunkWire:
        if self._fine_terrain_cache is None:
            return self._load_location_terrain(location_uid)
        return self._fine_terrain_cache.get_location_terrain(
            location_uid,
            lambda: self._load_location_terrain(location_uid),
        )

    def read_climate_coarse(self) -> ClimateFieldWire:
        path = self._paths.climate_coarse_path()
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_CLIMATE:
            raise ValueError(f"expected climate blob at {path}")
        return parse_climate_field_payload(payload)

    def chunk_exists(self, gx: int, gy: int, cx: int, cy: int) -> bool:
        return self._paths.wilderness_chunk_path(gx, gy, cx, cy).is_file()

    def _load_wilderness_chunk(self, gx: int, gy: int, cx: int, cy: int) -> FineTerrainChunkWire:
        path = self._paths.wilderness_chunk_path(gx, gy, cx, cy)
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_FINE_TERRAIN:
            raise ValueError(f"expected fine_terrain blob at {path}")
        return parse_fine_terrain_chunk_payload(payload)

    def _load_location_terrain(self, location_uid: str) -> FineTerrainChunkWire:
        path = self._paths.location_terrain_path(location_uid)
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_FINE_TERRAIN:
            raise ValueError(f"expected fine_terrain blob at {path}")
        return parse_fine_terrain_chunk_payload(payload)

    def _decode_file(self, path: Path) -> tuple[int, dict]:
        if not path.is_file():
            raise FileNotFoundError(f"pack blob not found: {path}")
        return self._codec.decode(path.read_bytes())
