"""Diagnostics for World Pack bake / fine-terrain refine — mirrors terrainParallelLog."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from app.application.worldData.terrainParallelLog import current_cpu_core

if TYPE_CHECKING:
    from app.application.worldData.generators.terrain.types import ColumnRect

logger = logging.getLogger(__name__)


def _rect_label(rect: ColumnRect) -> str:
    return f"x={rect.x_min}..{rect.x_max} y={rect.y_min}..{rect.y_max}"


def _async_task_name() -> str:
    try:
        task = asyncio.current_task()
        return task.get_name() if task is not None else "-"
    except RuntimeError:
        return "-"


def _diag_extra(
    *,
    activity: str,
    pool_workers: int | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Structured fields for JSON logs — thread / CPU / activity as top-level keys."""
    thread = threading.current_thread()
    extra: dict[str, Any] = {
        "activity": activity,
        "worker_thread": thread.name,
        "worker_tid": thread.ident,
        "cpu_core": current_cpu_core(),
        "asyncio_task": _async_task_name(),
    }
    if pool_workers is not None:
        extra["pool_workers"] = pool_workers
    extra.update(fields)
    return extra


def _info(msg: str, *args: Any, activity: str, pool_workers: int | None = None, **fields: Any) -> None:
    logger.info(msg, *args, extra=_diag_extra(activity=activity, pool_workers=pool_workers, **fields))


def _debug(msg: str, *args: Any, activity: str, pool_workers: int | None = None, **fields: Any) -> None:
    logger.debug(msg, *args, extra=_diag_extra(activity=activity, pool_workers=pool_workers, **fields))


def log_pack_compute_pool(*, workers: int, max_in_flight: int) -> None:
    _info(
        "pack compute pool | workers=%d max_in_flight=%d",
        workers,
        max_in_flight,
        activity="compute_pool_create",
        pool_workers=workers,
        max_in_flight=max_in_flight,
    )


def log_pack_bake_start(
    world_uid: str,
    *,
    tile_cap: int | None,
    tiles_planned: int,
    refine_scene: bool,
    locations: int,
    terrain_workers: int | None = None,
) -> float:
    _info(
        "pack bake start | world=%s tile_cap=%s tiles_planned=%d refine_scene=%s locations=%d terrain_workers=%s",
        world_uid,
        tile_cap if tile_cap is not None else "none",
        tiles_planned,
        refine_scene,
        locations,
        terrain_workers if terrain_workers is not None else "-",
        activity="bake_orchestrate",
        world_uid=world_uid,
        terrain_workers=terrain_workers,
    )
    return time.perf_counter()


def log_pack_surface_context(
    world_uid: str,
    *,
    ok: bool,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack surface context | world=%s ok=%s elapsed_ms=%.1f",
        world_uid,
        ok,
        elapsed_ms,
        activity="surface_context_prepare",
        world_uid=world_uid,
    )


def log_pack_drain_persisted_start(world_uid: str, *, max_jobs: int) -> float:
    _info(
        "pack drain persisted start | world=%s max_jobs=%d",
        world_uid,
        max_jobs,
        activity="drain_persisted_start",
        world_uid=world_uid,
        max_jobs=max_jobs,
    )
    return time.perf_counter()


def log_pack_drain_persisted_done(world_uid: str, *, processed: int, started_at: float) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack drain persisted done | world=%s processed=%d elapsed_ms=%.1f",
        world_uid,
        processed,
        elapsed_ms,
        activity="drain_persisted_done",
        world_uid=world_uid,
        processed=processed,
    )


def log_pack_world_map_bake_start(world_uid: str, *, tiles: int, cells_per_side: int) -> float:
    _info(
        "pack world_map bake start | world=%s tiles=%d cells_per_side=%d",
        world_uid,
        tiles,
        cells_per_side,
        activity="world_map_bake_start",
        world_uid=world_uid,
    )
    return time.perf_counter()


def log_pack_world_map_tile_done(
    world_uid: str,
    gx: int,
    gy: int,
    *,
    tile_idx: int,
    tiles_total: int,
    cells: int,
    content_hash: str | None,
    elapsed_ms: float,
) -> None:
    _info(
        "pack world_map tile done | world=%s tile=%d/%d gx=%d gy=%d cells=%d hash=%s elapsed_ms=%.1f",
        world_uid,
        tile_idx,
        tiles_total,
        gx,
        gy,
        cells,
        (content_hash or "")[:12] or "-",
        elapsed_ms,
        activity="world_map_tile_write",
        world_uid=world_uid,
        tile_gx=gx,
        tile_gy=gy,
    )


def log_pack_world_map_bake_done(
    world_uid: str,
    *,
    total_cells: int,
    tiles: int,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack world_map bake done | world=%s tiles=%d world_map_cells=%d elapsed_ms=%.1f",
        world_uid,
        tiles,
        total_cells,
        elapsed_ms,
        activity="world_map_bake_done",
        world_uid=world_uid,
    )


def log_pack_fine_terrain_phase_start(
    world_uid: str,
    phase: str,
    *,
    anchor_x: int,
    anchor_y: int,
    tile_gx: int,
    tile_gy: int,
    rects: int,
    heading: str | None = None,
    pool_workers: int | None = None,
) -> float:
    _info(
        "pack fine_terrain phase start | world=%s phase=%s anchor=(%d,%d) tile=(%d,%d) rects=%d heading=%s",
        world_uid,
        phase,
        anchor_x,
        anchor_y,
        tile_gx,
        tile_gy,
        rects,
        heading or "-",
        activity="fine_terrain_phase_start",
        world_uid=world_uid,
        phase=phase,
        pool_workers=pool_workers,
    )
    return time.perf_counter()


def log_pack_fine_terrain_workers(
    world_uid: str,
    *,
    phase: str,
    workers: int,
    chunks_total: int,
) -> None:
    _info(
        "pack fine_terrain parallel | world=%s phase=%s pool_workers=%d chunks_total=%d",
        world_uid,
        phase,
        workers,
        chunks_total,
        activity="fine_terrain_plan_parallel",
        world_uid=world_uid,
        phase=phase,
        pool_workers=workers,
        chunks_total=chunks_total,
    )


def log_pack_wilderness_chunk_start(
    world_uid: str,
    *,
    phase: str,
    tile_gx: int,
    tile_gy: int,
    chunk_idx: int,
    chunks_total: int,
    rect: ColumnRect,
    refine_role: str,
    pool_workers: int | None = None,
) -> float:
    _info(
        "pack wilderness_chunk generate start | world=%s phase=%s tile=(%d,%d) chunk=%d/%d role=%s rect=%s",
        world_uid,
        phase,
        tile_gx,
        tile_gy,
        chunk_idx,
        chunks_total,
        refine_role,
        _rect_label(rect),
        activity="wilderness_chunk_generate",
        world_uid=world_uid,
        phase=phase,
        pool_workers=pool_workers,
        chunk_idx=chunk_idx,
        chunks_total=chunks_total,
    )
    return time.perf_counter()


def log_pack_wilderness_chunk_persist(
    world_uid: str,
    *,
    phase: str,
    tile_gx: int,
    tile_gy: int,
    chunk_idx: int,
    chunks_total: int,
    refine_role: str,
    wilderness_cells: int,
    location_uids: list[str],
    pool_workers: int | None = None,
) -> None:
    _info(
        "pack wilderness_chunk persist start | world=%s phase=%s tile=(%d,%d) chunk=%d/%d role=%s "
        "wilderness=%d locations=%s",
        world_uid,
        phase,
        tile_gx,
        tile_gy,
        chunk_idx,
        chunks_total,
        refine_role,
        wilderness_cells,
        ",".join(location_uids) if location_uids else "-",
        activity="wilderness_chunk_persist_pack",
        world_uid=world_uid,
        phase=phase,
        pool_workers=pool_workers,
        chunk_idx=chunk_idx,
    )


def log_pack_wilderness_chunk_done(
    world_uid: str,
    *,
    phase: str,
    tile_gx: int,
    tile_gy: int,
    chunk_idx: int,
    chunks_total: int,
    rect: ColumnRect,
    refine_role: str,
    generated_cells: int,
    wilderness_cells: int,
    location_uids: list[str],
    started_at: float,
    pool_workers: int | None = None,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack wilderness_chunk done | world=%s phase=%s tile=(%d,%d) chunk=%d/%d role=%s "
        "rect=%s generated=%d wilderness=%d locations=%s elapsed_ms=%.1f",
        world_uid,
        phase,
        tile_gx,
        tile_gy,
        chunk_idx,
        chunks_total,
        refine_role,
        _rect_label(rect),
        generated_cells,
        wilderness_cells,
        ",".join(location_uids) if location_uids else "-",
        elapsed_ms,
        activity="wilderness_chunk_finalize",
        world_uid=world_uid,
        phase=phase,
        pool_workers=pool_workers,
        chunk_idx=chunk_idx,
    )


def log_pack_fine_terrain_phase_done(
    world_uid: str,
    phase: str,
    *,
    chunks_written: int,
    cells_total: int,
    started_at: float,
    pool_workers: int | None = None,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack fine_terrain phase done | world=%s phase=%s chunks_written=%d cells=%d elapsed_ms=%.1f",
        world_uid,
        phase,
        chunks_written,
        cells_total,
        elapsed_ms,
        activity="fine_terrain_phase_done",
        world_uid=world_uid,
        phase=phase,
        pool_workers=pool_workers,
    )


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


def log_pack_jobs_persisted(world_uid: str, *, count: int) -> None:
    _info(
        "pack jobs persisted | world=%s count=%d",
        world_uid,
        count,
        activity="jobs_persisted",
        world_uid=world_uid,
        job_count=count,
    )


def log_pack_location_terrain_persist(
    world_uid: str,
    *,
    location_uid: str,
    cells: int,
    pool_workers: int | None = None,
) -> None:
    _info(
        "pack location_terrain persist | world=%s location=%s cells=%d",
        world_uid,
        location_uid,
        cells,
        activity="location_terrain_persist_pack",
        world_uid=world_uid,
        location_uid=location_uid,
        pool_workers=pool_workers,
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


def log_pack_write_blob(
    kind: str,
    *,
    world_uid: str,
    path: str,
    nbytes: int,
    content_hash: str,
    extra: str = "",
) -> None:
    _debug(
        "pack write %s | world=%s path=%s bytes=%d hash=%s %s",
        kind,
        world_uid,
        path,
        nbytes,
        content_hash[:12],
        extra.strip(),
        activity=f"pack_write_{kind}",
        world_uid=world_uid,
        blob_kind=kind,
    )


def log_pack_manifest_saved(
    world_uid: str,
    *,
    content_hash: str | None,
    world_map_tiles: int,
    wilderness_chunks: int,
) -> None:
    _info(
        "pack manifest saved | world=%s hash=%s world_map_tiles=%d wilderness_chunks=%d",
        world_uid,
        (content_hash or "")[:12] or "-",
        world_map_tiles,
        wilderness_chunks,
        activity="manifest_saved",
        world_uid=world_uid,
    )


def log_pack_finalize(world_uid: str, *, pack_path: str, content_hash: str | None) -> None:
    _info(
        "pack finalize world row | world=%s path=%s hash=%s",
        world_uid,
        pack_path,
        (content_hash or "")[:12] or "-",
        activity="pack_finalize",
        world_uid=world_uid,
    )


def log_pack_climate_coarse_done(
    world_uid: str,
    *,
    samples: int,
    content_hash: str | None,
    started_at: float,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack climate_coarse bake done | world=%s samples=%d hash=%s elapsed_s=%.2f",
        world_uid,
        samples,
        (content_hash or "")[:12] or "-",
        elapsed_s,
        activity="climate_coarse_bake",
        world_uid=world_uid,
        climate_samples=samples,
        elapsed_s=round(elapsed_s, 2),
    )


def log_pack_climate_tile_done(
    world_uid: str,
    *,
    tile_gx: int,
    tile_gy: int,
    samples: int,
) -> None:
    _info(
        "pack climate_tile bake done | world=%s tile=(%d,%d) samples=%d",
        world_uid,
        tile_gx,
        tile_gy,
        samples,
        activity="climate_tile_bake",
        world_uid=world_uid,
        tile_gx=tile_gx,
        tile_gy=tile_gy,
        climate_samples=samples,
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
