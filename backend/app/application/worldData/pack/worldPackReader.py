"""Read World Pack blobs and manifest."""

from __future__ import annotations

from pathlib import Path

from app.application.worldData.pack.packBlobWire import (
    parse_climate_field_payload,
    parse_l0_tile_payload,
    parse_l2_chunk_payload,
)
from app.application.worldData.pack.packL2DecodeCache import PackL2DecodeCache
from app.application.worldData.pack.packManifestStore import PackManifestStore
from app.application.worldData.pack.tileCodec import (
    PAYLOAD_KIND_CLIMATE,
    PAYLOAD_KIND_L0,
    PAYLOAD_KIND_L2,
    TileCodec,
)
from app.application.worldData.pack.worldPackPaths import WorldPackPaths
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire
from app.dataModel.worldPack.l2ChunkWire import L2ChunkWire
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.worldPackManifest import WorldPackManifest


class WorldPackReader:
    def __init__(
        self,
        paths: WorldPackPaths,
        *,
        codec: TileCodec | None = None,
        store: PackManifestStore | None = None,
        l2_cache: PackL2DecodeCache | None = None,
    ) -> None:
        self._paths = paths
        self._codec = codec or TileCodec()
        self._store = store or PackManifestStore()
        self._l2_cache = l2_cache
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

    def read_l0_tile(self, gx: int, gy: int) -> tuple[int, list[WorldMapCellWire]]:
        path = self._paths.l0_tile_path(gx, gy)
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_L0:
            raise ValueError(f"expected L0 blob at {path}")
        return parse_l0_tile_payload(payload)

    def read_l2_chunk(self, gx: int, gy: int, cx: int, cy: int) -> L2ChunkWire:
        if self._l2_cache is None:
            return self._load_l2_chunk(gx, gy, cx, cy)
        return self._l2_cache.get_wilderness_chunk(
            (gx, gy, cx, cy),
            lambda: self._load_l2_chunk(gx, gy, cx, cy),
        )

    def read_location_l2(self, location_uid: str) -> L2ChunkWire:
        if self._l2_cache is None:
            return self._load_location_l2(location_uid)
        return self._l2_cache.get_location_l2(
            location_uid,
            lambda: self._load_location_l2(location_uid),
        )

    def read_climate_coarse(self) -> ClimateFieldWire:
        path = self._paths.climate_coarse_path()
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_CLIMATE:
            raise ValueError(f"expected climate blob at {path}")
        return parse_climate_field_payload(payload)

    def chunk_exists(self, gx: int, gy: int, cx: int, cy: int) -> bool:
        return self._paths.l2_chunk_path(gx, gy, cx, cy).is_file()

    def _load_l2_chunk(self, gx: int, gy: int, cx: int, cy: int) -> L2ChunkWire:
        path = self._paths.l2_chunk_path(gx, gy, cx, cy)
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_L2:
            raise ValueError(f"expected L2 blob at {path}")
        return parse_l2_chunk_payload(payload)

    def _load_location_l2(self, location_uid: str) -> L2ChunkWire:
        path = self._paths.location_l2_path(location_uid)
        kind, payload = self._decode_file(path)
        if kind != PAYLOAD_KIND_L2:
            raise ValueError(f"expected L2 blob at {path}")
        return parse_l2_chunk_payload(payload)

    def _decode_file(self, path: Path) -> tuple[int, dict]:
        if not path.is_file():
            raise FileNotFoundError(f"pack blob not found: {path}")
        return self._codec.decode(path.read_bytes())
