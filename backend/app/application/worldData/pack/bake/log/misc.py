"""Bake orchestration glue — start/done, refine queue, worker, loading."""

from __future__ import annotations

import time
from typing import Any

from ._shared import _debug, _info


def log_pack_bake_start(
    world_uid: str,
    *,
    tile_cap: int | None,
    tiles_planned: int,
    locations: int,
    terrain_workers: int | None = None,
    climate_workers: int | None = None,
) -> float:
    _info(
        "pack bake start | world=%s tile_cap=%s tiles_planned=%d locations=%d "
        "terrain_workers=%s climate_workers=%s",
        world_uid,
        tile_cap if tile_cap is not None else "none",
        tiles_planned,
        locations,
        terrain_workers if terrain_workers is not None else "-",
        climate_workers if climate_workers is not None else "-",
        activity="bake_orchestrate",
        world_uid=world_uid,
        terrain_workers=terrain_workers,
        climate_workers=climate_workers,
    )
    return time.perf_counter()


def log_pack_queue_scheduled(
    world_uid: str,
    kind: str,
    *,
    enqueued: int,
    queue_depth: int,
) -> None:
    _info(
        "pack queue scheduled | world=%s kind=%s enqueued=%d queue_depth=%d",
        world_uid,
        kind,
        enqueued,
        queue_depth,
        activity="queue_scheduled",
        world_uid=world_uid,
        queue_kind=kind,
    )


def log_pack_queue_enqueue(
    world_uid: str,
    gx: int,
    gy: int,
    cx: int,
    cy: int,
    *,
    priority: float,
) -> None:
    _debug(
        "pack queue enqueue | world=%s tile=(%d,%d) chunk=(%d,%d) priority=%.1f",
        world_uid,
        gx,
        gy,
        cx,
        cy,
        priority,
        activity="queue_enqueue",
        world_uid=world_uid,
        tile_gx=gx,
        tile_gy=gy,
        chunk_cx=cx,
        chunk_cy=cy,
    )


def log_pack_worker_chunk(
    world_uid: str,
    *,
    activity: str,
    tile_gx: int,
    tile_gy: int,
    chunk_cx: int,
    chunk_cy: int,
    cells: int,
    job: str | None = None,
) -> None:
    _info(
        "pack worker chunk | world=%s tile=(%d,%d) chunk=(%d,%d) cells=%d%s",
        world_uid,
        tile_gx,
        tile_gy,
        chunk_cx,
        chunk_cy,
        cells,
        f" job={job}" if job else "",
        activity=activity,
        world_uid=world_uid,
        tile_gx=tile_gx,
        tile_gy=tile_gy,
        chunk_cx=chunk_cx,
        chunk_cy=chunk_cy,
        job_uid=job,
    )


def log_pack_drain_queue_start(world_uid: str, *, max_jobs: int, pending: int) -> float:
    _info(
        "pack drain queue start | world=%s max_jobs=%d pending=%d",
        world_uid,
        max_jobs,
        pending,
        activity="drain_queue_start",
        world_uid=world_uid,
        max_jobs=max_jobs,
        pending=pending,
    )
    return time.perf_counter()


def log_pack_drain_queue_done(world_uid: str, *, processed: int, started_at: float) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack drain queue done | world=%s processed=%d elapsed_ms=%.1f",
        world_uid,
        processed,
        elapsed_ms,
        activity="drain_queue_done",
        world_uid=world_uid,
        processed=processed,
    )


def log_pack_bake_done(
    world_uid: str,
    *,
    world_map_cells: int,
    chunks_done: int,
    chunks_total: int,
    queue_depth: int,
    started_at: float,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack bake done | world=%s world_map_cells=%d chunks=%d/%d queue=%d elapsed_s=%.2f",
        world_uid,
        world_map_cells,
        chunks_done,
        chunks_total,
        queue_depth,
        elapsed_s,
        activity="bake_orchestrate_done",
        world_uid=world_uid,
        elapsed_s=round(elapsed_s, 2),
    )


def log_pack_entry_anchor_fallback(
    world_uid: str,
    *,
    reason: str,
    anchor_x: int,
    anchor_y: int,
) -> None:
    """Light bake fell back to a default entry coordinate (usually 0,0)."""
    _info(
        "pack entry anchor fallback | world=%s anchor=(%d,%d) reason=%s",
        world_uid,
        anchor_x,
        anchor_y,
        reason,
        activity="entry_anchor_fallback",
        world_uid=world_uid,
        anchor_x=anchor_x,
        anchor_y=anchor_y,
        reason=reason,
    )


def log_pack_loading_progress(
    world_uid: str,
    *,
    phase: str,
    tiles_pct: float,
    locations_pct: float,
    wilderness_pct: float,
    tiles_ready: int = 0,
    tiles_total: int = 0,
    locations_ready: int = 0,
    locations_total: int = 0,
    wilderness_ready: int = 0,
    wilderness_total: int = 0,
    refine_pct: float | None = None,
) -> None:
    """WP-15 — tiles / locations / wilderness percent snapshot (INFO)."""
    refine_part = ""
    fields: dict[str, Any] = {
        "world_uid": world_uid,
        "phase": phase,
        "tiles_pct": tiles_pct,
        "locations_pct": locations_pct,
        "wilderness_pct": wilderness_pct,
        "tiles_ready": tiles_ready,
        "tiles_total": tiles_total,
        "locations_ready": locations_ready,
        "locations_total": locations_total,
        "wilderness_ready": wilderness_ready,
        "wilderness_total": wilderness_total,
    }
    if refine_pct is not None:
        refine_part = f" refine={refine_pct:.1f}%"
        fields["refine_pct"] = refine_pct
    _info(
        "pack loading progress | world=%s phase=%s tiles=%.1f%% locations=%.1f%% wilderness=%.1f%%%s"
        " (%d/%d tiles, %d/%d locs, %d/%d wild)",
        world_uid,
        phase,
        tiles_pct,
        locations_pct,
        wilderness_pct,
        refine_part,
        tiles_ready,
        tiles_total,
        locations_ready,
        locations_total,
        wilderness_ready,
        wilderness_total,
        activity="loading_progress",
        **fields,
    )
