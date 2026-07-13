"""Pack loading progress snapshot — WP-15 / REVIEW-5."""

from __future__ import annotations

import json

from app.application.worldData.loadingProgress import (
    LoadingPhase,
    LoadingProgressSnapshot,
    LocalGridLoading,
    WorldMapLoading,
    progress_pct,
)
from app.application.worldData.pack.bake.packBakeLog import log_pack_loading_progress
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.models.world import World


def _locations_total(reader) -> int:
    path = reader.paths.locations_index_path()
    if not path.is_file():
        return 0
    raw = json.loads(path.read_text(encoding="utf-8"))
    index = LocationsIndexWire.model_validate(raw)
    return len(index.locations)


def _wilderness_score(tiles) -> tuple[int, int, float]:
    """Weighted ready count: complete=1, partial=0.5 → pct over tile count."""
    total = len(tiles)
    if total <= 0:
        return 0, 0, 100.0
    weighted = 0.0
    ready_units = 0
    for tile in tiles:
        status = tile.wilderness_refine_status
        if status == "complete":
            weighted += 1.0
            ready_units += 1
        elif status == "partial":
            weighted += 0.5
    return ready_units, total, round(100.0 * weighted / total, 1)


def _world_map_phase(
    tiles_pct: float,
    locations_pct: float,
    wilderness_pct: float,
) -> LoadingPhase:
    if tiles_pct < 100.0:
        return "tiles"
    if locations_pct < 100.0:
        return "locations"
    if wilderness_pct < 100.0:
        return "wilderness"
    return "idle"


class PackLoadingProgressFacade:
    def __init__(self, context: PackReadContext) -> None:
        self._ctx = context

    def get_loading_progress(self, world: World) -> LoadingProgressSnapshot:
        if not self._ctx.has_pack_for(world):
            return LoadingProgressSnapshot(world_uid=world.world_uid)
        reader = self._ctx.reader_for(world)
        manifest = reader.manifest
        tiles = list(manifest.tiles)

        tiles_ready = sum(1 for t in tiles if t.world_map_path)
        tiles_total = len(tiles) if tiles else tiles_ready
        tiles_pct = progress_pct(tiles_ready, tiles_total)

        locations_total = _locations_total(reader)
        locations_ready = sum(
            1 for loc in manifest.location_terrain_entries if loc.terrain_path
        )
        locations_pct = progress_pct(locations_ready, locations_total)

        wilderness_ready, wilderness_total, wilderness_pct = _wilderness_score(tiles)

        chunks_ready = manifest.wilderness_chunks_baked
        chunks_total = sum(len(t.chunks) for t in tiles) if tiles else chunks_ready
        chunks_total = max(chunks_total, chunks_ready)
        refine_pct = progress_pct(chunks_ready, chunks_total)

        has_coarse = reader.paths.climate_coarse_path().is_file()
        any_fine = any(t.climate_status == "fine" for t in tiles)
        phase = _world_map_phase(tiles_pct, locations_pct, wilderness_pct)
        local_phase: LoadingPhase = "wilderness" if refine_pct < 100.0 else "idle"

        log_pack_loading_progress(
            world.world_uid,
            phase=phase,
            tiles_pct=tiles_pct,
            locations_pct=locations_pct,
            wilderness_pct=wilderness_pct,
            tiles_ready=tiles_ready,
            tiles_total=tiles_total,
            locations_ready=locations_ready,
            locations_total=locations_total,
            wilderness_ready=wilderness_ready,
            wilderness_total=wilderness_total,
            refine_pct=refine_pct,
        )

        return LoadingProgressSnapshot(
            world_uid=world.world_uid,
            has_climate_coarse=has_coarse,
            world_map=WorldMapLoading(
                phase=phase,
                tiles_pct=tiles_pct,
                locations_pct=locations_pct,
                wilderness_pct=wilderness_pct,
                tiles_ready=tiles_ready,
                tiles_total=tiles_total,
                locations_ready=locations_ready,
                locations_total=locations_total,
                wilderness_ready=wilderness_ready,
                wilderness_total=wilderness_total,
            ),
            local_grid=LocalGridLoading(
                phase=local_phase,
                refine_pct=refine_pct,
                chunks_ready=chunks_ready,
                chunks_total=chunks_total,
                climate_status="fine_ready" if any_fine else ("coarse_only" if has_coarse else None),
            ),
        )
