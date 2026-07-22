"""Write World Pack blobs and manifest — WP-7 atomic commit."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from app.application.worldData.pack.io.packBlobWire import (
    climate_field_payload,
    world_map_tile_payload,
    fine_terrain_chunk_payload,
)
from app.application.worldData.pack.io.packManifestStore import PackManifestStore
from app.application.worldData.pack.bake.packBakeLog import log_pack_manifest_saved, log_pack_write_blob
from app.application.worldData.pack.io.tileCodec import (
    PAYLOAD_KIND_CLIMATE,
    PAYLOAD_KIND_WORLD_MAP,
    PAYLOAD_KIND_FINE_TERRAIN,
    TileCodec,
)
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.read.parentLightCache import ParentLightCache
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire
from app.dataModel.worldPack.wildernessRefineStatus import (
    wilderness_refine_status_for_counts,
    wilderness_refine_status_without_expected,
)
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.worldPackManifest import (
    ChunkRef,
    ChunkRefineRole,
    TileManifestEntry,
    WildernessRefineStatus,
    WorldPackManifest,
)
from app.db.models.world import World


class WorldPackWriter:
    """Atomic pack writer. Prefer Container.world_pack_writer_for so parent-light
    cache is process-scoped; constructing with bare paths creates a private cache.
    """

    def __init__(
        self,
        paths: WorldPackPaths,
        *,
        manifest: WorldPackManifest | None = None,
        codec: TileCodec | None = None,
        store: PackManifestStore | None = None,
        bake_defaults: PackBakeDefaults | None = None,
        parent_light_cache: ParentLightCache | None = None,
    ) -> None:
        self._paths = paths
        defaults = bake_defaults or PackBakeDefaults.canonical_defaults()
        self._codec = codec or TileCodec(level=defaults.zstd_level)
        self._store = store or PackManifestStore()
        self._bake_defaults = defaults
        self._parent_light_cache = parent_light_cache or ParentLightCache()
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

    @property
    def paths(self) -> WorldPackPaths:
        return self._paths

    @property
    def parent_light_cache(self) -> ParentLightCache:
        return self._parent_light_cache

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

    def write_world_map_tile(
        self,
        gx: int,
        gy: int,
        cells: list[WorldMapCellWire],
        *,
        cells_per_side: int,
    ) -> str:
        payload = world_map_tile_payload(cells_per_side, cells)
        blob = self._codec.encode(PAYLOAD_KIND_WORLD_MAP, payload)
        path = self._paths.world_map_tile_path(gx, gy)
        content_hash = self._atomic_write(path, blob)
        log_pack_write_blob(
            "world_map",
            world_uid=self._paths.world_uid,
            path=path.relative_to(self._paths.root).as_posix(),
            nbytes=len(blob),
            content_hash=content_hash,
            extra=f"gx={gx} gy={gy} cells={len(cells)}",
        )
        tile = self._upsert_tile(gx, gy)
        rel = path.relative_to(self._paths.root).as_posix()
        updated = tile.model_copy(
            update={"world_map_path": rel, "world_map_hash": content_hash},
        )
        self._replace_tile(updated)
        self._manifest.world_map_cells_per_tile = cells_per_side
        if self._manifest.map_cell_size_m is None or int(self._manifest.map_cell_size_m) < 1:
            raise ValueError(
                "manifest.map_cell_size_m required before write_world_map_tile "
                "(cannot cache parent light with tile_m fallback)",
            )
        tile_m = int(self._manifest.map_cell_size_m)
        self._parent_light_cache.put(
            ParentLightTile.from_cells(
                world_uid=self._paths.world_uid,
                gx=gx,
                gy=gy,
                side=cells_per_side,
                tile_m=tile_m,
                cells=cells,
            ),
        )
        return content_hash

    def write_wilderness_chunk(
        self,
        gx: int,
        gy: int,
        chunk: FineTerrainChunkWire,
        *,
        refine_role: ChunkRefineRole = "background",
    ) -> str:
        blob = self._codec.encode(PAYLOAD_KIND_FINE_TERRAIN, fine_terrain_chunk_payload(chunk))
        path = self._paths.wilderness_chunk_path(gx, gy, chunk.cx, chunk.cy)
        content_hash = self._atomic_write(path, blob)
        log_pack_write_blob(
            "wilderness_chunk",
            world_uid=self._paths.world_uid,
            path=path.relative_to(self._paths.root).as_posix(),
            nbytes=len(blob),
            content_hash=content_hash,
            extra=f"tile=({gx},{gy}) chunk=({chunk.cx},{chunk.cy}) role={refine_role}",
        )
        self.commit_chunk(
            gx, gy, chunk.cx, chunk.cy,
            content_hash=content_hash,
            nbytes=len(blob),
            refine_role=refine_role,
        )
        return content_hash

    def write_location_terrain(
        self,
        location_uid: str,
        columns: FineTerrainChunkWire,
        *,
        territory_volume,
    ) -> str:
        from app.dataModel.worldPack.worldPackManifest import LocationTerrainEntry

        blob = self._codec.encode(PAYLOAD_KIND_FINE_TERRAIN, fine_terrain_chunk_payload(columns))
        path = self._paths.location_terrain_path(location_uid)
        content_hash = self._atomic_write(path, blob)
        rel = path.relative_to(self._paths.root).as_posix()
        log_pack_write_blob(
            "location_terrain",
            world_uid=self._paths.world_uid,
            path=rel,
            nbytes=len(blob),
            content_hash=content_hash,
            extra=f"location={location_uid}",
        )
        entry = LocationTerrainEntry(
            location_uid=location_uid,
            territory_volume=territory_volume,
            terrain_path=rel,
            terrain_hash=content_hash,
            bytes=len(blob),
        )
        self._manifest.location_terrain_entries = [
            loc for loc in self._manifest.location_terrain_entries if loc.location_uid != location_uid
        ]
        self._manifest.location_terrain_entries.append(entry)
        return content_hash

    def write_climate_coarse(self, field: ClimateFieldWire) -> str:
        blob = self._codec.encode(PAYLOAD_KIND_CLIMATE, climate_field_payload(field))
        path = self._paths.climate_coarse_path()
        content_hash = self._atomic_write(path, blob)
        log_pack_write_blob(
            "climate_coarse",
            world_uid=self._paths.world_uid,
            path=path.relative_to(self._paths.root).as_posix(),
            nbytes=len(blob),
            content_hash=content_hash,
            extra=f"climate_status={field.climate_status} samples={len(field.samples)}",
        )
        return content_hash

    def write_climate_tile(self, gx: int, gy: int, field: ClimateFieldWire) -> str:
        blob = self._codec.encode(PAYLOAD_KIND_CLIMATE, climate_field_payload(field))
        path = self._paths.climate_tile_path(gx, gy)
        content_hash = self._atomic_write(path, blob)
        log_pack_write_blob(
            "climate_tile",
            world_uid=self._paths.world_uid,
            path=path.relative_to(self._paths.root).as_posix(),
            nbytes=len(blob),
            content_hash=content_hash,
            extra=f"tile=({gx},{gy}) climate_status={field.climate_status}",
        )
        tile = self._upsert_tile(gx, gy)
        updated = tile.model_copy(update={"climate_status": "fine"})
        self._replace_tile(updated)
        return content_hash

    def write_locations_index(self, index: LocationsIndexWire) -> Path:
        """Write locations_index.json — POJO is wire source of truth."""
        path = self._paths.locations_index_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            index.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

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
        """Append/replace chunk ref; status via ``recalc_wilderness_status`` (single writer)."""
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
        self._replace_tile(tile.model_copy(update={"chunks": chunks}))
        # Unknown full-tile expected → provisional partial/absent (entry/rings).
        self.recalc_wilderness_status(gx, gy, expected_chunks=None)

    def recalc_wilderness_status(
        self,
        gx: int,
        gy: int,
        *,
        expected_chunks: int | None = None,
    ) -> WildernessRefineStatus:
        """Sole setter for ``wilderness_refine_status`` (WP-12).

        ``expected_chunks is None`` → entry/runtime provisional status.
        Otherwise → complete/partial/absent from baked vs expected counts.
        """
        tile = self._upsert_tile(gx, gy)
        if expected_chunks is None:
            status = wilderness_refine_status_without_expected(len(tile.chunks))
        else:
            status = wilderness_refine_status_for_counts(len(tile.chunks), expected_chunks)
        if tile.wilderness_refine_status == status:
            return status
        self._replace_tile(tile.model_copy(update={"wilderness_refine_status": status}))
        return status

    def recalc_manifest_counters(self) -> None:
        side = self._manifest.world_map_cells_per_tile
        world_map_cells = 0
        for tile in self._manifest.tiles:
            if tile.world_map_path:
                world_map_cells += side * side
        self._manifest.world_map_cells = world_map_cells
        self._manifest.wilderness_chunks_baked = sum(len(t.chunks) for t in self._manifest.tiles)

    def save_manifest(self) -> None:
        self.recalc_manifest_counters()
        payload = self._manifest.model_dump(mode="json")
        payload["content_hash"] = None
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self._manifest.content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        self._store.save(self._paths.manifest_path(), self._manifest)
        log_pack_manifest_saved(
            self._paths.world_uid,
            content_hash=self._manifest.content_hash,
            world_map_tiles=sum(1 for t in self._manifest.tiles if t.world_map_path),
            wilderness_chunks=self._manifest.wilderness_chunks_baked,
        )

    def pack_storage_path(self) -> str:
        return f"worlds/{self._paths.world_uid}/pack"

    def _replace_tile(self, entry: TileManifestEntry) -> None:
        self._manifest.tiles = [
            t for t in self._manifest.tiles if not (t.gx == entry.gx and t.gy == entry.gy)
        ]
        self._manifest.tiles.append(entry)
