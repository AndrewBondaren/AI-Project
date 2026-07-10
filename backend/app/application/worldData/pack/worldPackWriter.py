"""Write World Pack blobs and manifest — WP-7 atomic commit."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from app.application.worldData.pack.packBlobWire import (
    climate_field_payload,
    l0_tile_payload,
    l2_chunk_payload,
)
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
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.worldPackManifest import (
    ChunkRef,
    ChunkRefineRole,
    TileManifestEntry,
    WorldPackManifest,
)
from app.db.models.world import World


class WorldPackWriter:
    def __init__(
        self,
        paths: WorldPackPaths,
        *,
        manifest: WorldPackManifest | None = None,
        codec: TileCodec | None = None,
        store: PackManifestStore | None = None,
        bake_defaults: PackBakeDefaults | None = None,
    ) -> None:
        self._paths = paths
        defaults = bake_defaults or PackBakeDefaults.canonical_defaults()
        self._codec = codec or TileCodec(level=defaults.zstd_level)
        self._store = store or PackManifestStore()
        self._bake_defaults = defaults
        if manifest is not None:
            self._manifest = manifest
        elif self._store.exists(paths.manifest_path()):
            self._manifest = self._store.load(paths.manifest_path())
        else:
            self._manifest = WorldPackManifest(world_uid=paths.world_uid)
        self._paths.ensure_dirs()

    @property
    def manifest(self) -> WorldPackManifest:
        return self._manifest

    def sync_world_metadata(self, world: World, *, cells_per_side: int) -> None:
        self._manifest.map_cell_size_m = world.map_cell_size_m
        self._manifest.world_map_cells_per_tile = cells_per_side
        if world.world_map_cells_per_tile is not None:
            self._manifest.world_map_cells_per_tile = world.world_map_cells_per_tile
        self._manifest.codec_version = self._bake_defaults.codec_version
        self._manifest.payload_format = "json"

    def _atomic_write(self, target: Path, data: bytes) -> str:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return self._codec.content_hash(data)

    def _upsert_tile(self, gx: int, gy: int) -> TileManifestEntry:
        for tile in self._manifest.tiles:
            if tile.gx == gx and tile.gy == gy:
                return tile
        entry = TileManifestEntry(gx=gx, gy=gy)
        self._manifest.tiles.append(entry)
        return entry

    def write_l0_world_map(
        self,
        gx: int,
        gy: int,
        cells: list[WorldMapCellWire],
        *,
        cells_per_side: int,
    ) -> str:
        payload = l0_tile_payload(cells_per_side, cells)
        blob = self._codec.encode(PAYLOAD_KIND_L0, payload)
        path = self._paths.l0_tile_path(gx, gy)
        content_hash = self._atomic_write(path, blob)
        tile = self._upsert_tile(gx, gy)
        rel = path.relative_to(self._paths.root).as_posix()
        updated = tile.model_copy(
            update={"l0_path": rel, "l0_hash": content_hash},
        )
        self._replace_tile(updated)
        self._manifest.world_map_cells_per_tile = cells_per_side
        return content_hash

    def write_l2_wilderness_chunk(
        self,
        gx: int,
        gy: int,
        chunk: L2ChunkWire,
        *,
        refine_role: ChunkRefineRole = "background",
    ) -> str:
        blob = self._codec.encode(PAYLOAD_KIND_L2, l2_chunk_payload(chunk))
        path = self._paths.l2_chunk_path(gx, gy, chunk.cx, chunk.cy)
        content_hash = self._atomic_write(path, blob)
        self.commit_chunk(
            gx, gy, chunk.cx, chunk.cy,
            content_hash=content_hash,
            nbytes=len(blob),
            refine_role=refine_role,
        )
        return content_hash

    def write_location_l2(
        self,
        location_uid: str,
        columns: L2ChunkWire,
        *,
        territory_volume,
    ) -> str:
        from app.dataModel.worldPack.worldPackManifest import LocationL2Entry

        blob = self._codec.encode(PAYLOAD_KIND_L2, l2_chunk_payload(columns))
        path = self._paths.location_l2_path(location_uid)
        content_hash = self._atomic_write(path, blob)
        rel = path.relative_to(self._paths.root).as_posix()
        entry = LocationL2Entry(
            location_uid=location_uid,
            territory_volume=territory_volume,
            terrain_path=rel,
            content_hash=content_hash,
            bytes=len(blob),
        )
        self._manifest.locations_l2 = [
            loc for loc in self._manifest.locations_l2 if loc.location_uid != location_uid
        ]
        self._manifest.locations_l2.append(entry)
        return content_hash

    def write_climate_coarse(self, field: ClimateFieldWire) -> str:
        blob = self._codec.encode(PAYLOAD_KIND_CLIMATE, climate_field_payload(field))
        path = self._paths.climate_coarse_path()
        return self._atomic_write(path, blob)

    def commit_chunk(
        self,
        gx: int,
        gy: int,
        cx: int,
        cy: int,
        *,
        content_hash: str | None = None,
        nbytes: int | None = None,
        refine_role: ChunkRefineRole | None = None,
    ) -> None:
        tile = self._upsert_tile(gx, gy)
        chunks = [c for c in tile.chunks if not (c.cx == cx and c.cy == cy)]
        chunks.append(
            ChunkRef(
                cx=cx,
                cy=cy,
                refine_role=refine_role,
                content_hash=content_hash,
                bytes=nbytes,
            ),
        )
        updated = tile.model_copy(update={"chunks": chunks, "l2_status": "partial"})
        self._replace_tile(updated)

    def recalc_manifest_counters(self) -> None:
        side = self._manifest.world_map_cells_per_tile
        l0_cells = 0
        for tile in self._manifest.tiles:
            if tile.l0_path:
                l0_cells += side * side
        self._manifest.l0_cells = l0_cells
        self._manifest.l2_chunks_baked = sum(len(t.chunks) for t in self._manifest.tiles)

    def save_manifest(self) -> None:
        self.recalc_manifest_counters()
        payload = self._manifest.model_dump(mode="json")
        payload["content_hash"] = None
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self._manifest.content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        self._store.save(self._paths.manifest_path(), self._manifest)

    def pack_storage_path(self) -> str:
        return f"worlds/{self._paths.world_uid}/pack"

    def _replace_tile(self, entry: TileManifestEntry) -> None:
        self._manifest.tiles = [
            t for t in self._manifest.tiles if not (t.gx == entry.gx and t.gy == entry.gy)
        ]
        self._manifest.tiles.append(entry)
