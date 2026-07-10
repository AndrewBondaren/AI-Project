"""Diagnostics for World Pack bake / L2 refine — mirrors terrainParallelLog."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING

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


def _thread_diag(*, activity: str) -> str:
    """Compact thread + CPU label for log lines."""
    cpu = current_cpu_core()
    cpu_s = str(cpu) if cpu is not None else "?"
    thread = threading.current_thread()
    return (
        f"activity={activity} thread={thread.name} tid={thread.ident} "
        f"cpu={cpu_s} asyncio_task={_async_task_name()}"
    )


def log_pack_bake_start(
    world_uid: str,
    *,
    tile_cap: int | None,
    tiles_planned: int,
    refine_scene: bool,
    locations: int,
) -> float:
    logger.info(
        "pack bake start | world=%s tile_cap=%s tiles_planned=%d refine_scene=%s locations=%d %s",
        world_uid,
        tile_cap if tile_cap is not None else "none",
        tiles_planned,
        refine_scene,
        locations,
        _thread_diag(activity="bake_orchestrate"),
    )
    return time.perf_counter()


def log_pack_surface_context(
    world_uid: str,
    *,
    ok: bool,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "pack surface context | world=%s ok=%s elapsed_ms=%.1f",
        world_uid,
        ok,
        elapsed_ms,
    )


def log_pack_drain_persisted_start(world_uid: str, *, max_jobs: int) -> None:
    logger.info(
        "pack drain persisted start | world=%s max_jobs=%d",
        world_uid,
        max_jobs,
    )


def log_pack_l0_bake_start(world_uid: str, *, tiles: int, cells_per_side: int) -> float:
    logger.info(
        "pack l0 bake start | world=%s tiles=%d cells_per_side=%d",
        world_uid,
        tiles,
        cells_per_side,
    )
    return time.perf_counter()


def log_pack_l0_tile_done(
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
    logger.info(
        "pack l0 tile done | world=%s tile=%d/%d gx=%d gy=%d cells=%d hash=%s elapsed_ms=%.1f %s",
        world_uid,
        tile_idx,
        tiles_total,
        gx,
        gy,
        cells,
        (content_hash or "")[:12] or "-",
        elapsed_ms,
        _thread_diag(activity="l0_tile_write"),
    )


def log_pack_l0_bake_done(
    world_uid: str,
    *,
    total_cells: int,
    tiles: int,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "pack l0 bake done | world=%s tiles=%d l0_cells=%d elapsed_ms=%.1f",
        world_uid,
        tiles,
        total_cells,
        elapsed_ms,
    )


def log_pack_l2_phase_start(
    world_uid: str,
    phase: str,
    *,
    anchor_x: int,
    anchor_y: int,
    tile_gx: int,
    tile_gy: int,
    rects: int,
    heading: str | None = None,
) -> float:
    logger.info(
        "pack l2 phase start | world=%s phase=%s anchor=(%d,%d) tile=(%d,%d) rects=%d heading=%s",
        world_uid,
        phase,
        anchor_x,
        anchor_y,
        tile_gx,
        tile_gy,
        rects,
        heading or "-",
    )
    return time.perf_counter()


def log_pack_l2_workers(
    world_uid: str,
    *,
    phase: str,
    workers: int,
    chunks_total: int,
) -> None:
    logger.info(
        "pack l2 parallel | world=%s phase=%s pool_workers=%d chunks_total=%d %s",
        world_uid,
        phase,
        workers,
        chunks_total,
        _thread_diag(activity="l2_plan_parallel"),
    )


def log_pack_l2_chunk_start(
    world_uid: str,
    *,
    phase: str,
    tile_gx: int,
    tile_gy: int,
    chunk_idx: int,
    chunks_total: int,
    rect: ColumnRect,
    refine_role: str,
) -> float:
    logger.info(
        "pack l2 chunk generate start | world=%s phase=%s tile=(%d,%d) chunk=%d/%d role=%s "
        "rect=%s %s",
        world_uid,
        phase,
        tile_gx,
        tile_gy,
        chunk_idx,
        chunks_total,
        refine_role,
        _rect_label(rect),
        _thread_diag(activity="l2_chunk_generate"),
    )
    return time.perf_counter()


def log_pack_l2_chunk_persist(
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
) -> None:
    logger.info(
        "pack l2 chunk persist start | world=%s phase=%s tile=(%d,%d) chunk=%d/%d role=%s "
        "wilderness=%d locations=%s %s",
        world_uid,
        phase,
        tile_gx,
        tile_gy,
        chunk_idx,
        chunks_total,
        refine_role,
        wilderness_cells,
        ",".join(location_uids) if location_uids else "-",
        _thread_diag(activity="l2_chunk_persist_pack"),
    )


def log_pack_l2_chunk_done(
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
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "pack l2 chunk done | world=%s phase=%s tile=(%d,%d) chunk=%d/%d role=%s "
        "rect=%s generated=%d wilderness=%d locations=%s elapsed_ms=%.1f %s",
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
        _thread_diag(activity="l2_chunk_finalize"),
    )


def log_pack_l2_phase_done(
    world_uid: str,
    phase: str,
    *,
    chunks_written: int,
    cells_total: int,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "pack l2 phase done | world=%s phase=%s chunks_written=%d cells=%d elapsed_ms=%.1f",
        world_uid,
        phase,
        chunks_written,
        cells_total,
        elapsed_ms,
    )


def log_pack_queue_scheduled(
    world_uid: str,
    kind: str,
    *,
    enqueued: int,
    queue_depth: int,
) -> None:
    logger.info(
        "pack queue scheduled | world=%s kind=%s enqueued=%d queue_depth=%d",
        world_uid,
        kind,
        enqueued,
        queue_depth,
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
    logger.debug(
        "pack queue enqueue | world=%s tile=(%d,%d) chunk=(%d,%d) priority=%.1f",
        world_uid,
        gx,
        gy,
        cx,
        cy,
        priority,
    )


def log_pack_jobs_persisted(world_uid: str, *, count: int) -> None:
    logger.info(
        "pack jobs persisted | world=%s count=%d",
        world_uid,
        count,
    )


def log_pack_l2_location_persist(
    world_uid: str,
    *,
    location_uid: str,
    cells: int,
) -> None:
    logger.info(
        "pack l2 location persist | world=%s location=%s cells=%d %s",
        world_uid,
        location_uid,
        cells,
        _thread_diag(activity="l2_location_persist_pack"),
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
    job_s = f" job={job}" if job else ""
    logger.info(
        "pack worker chunk | world=%s tile=(%d,%d) chunk=(%d,%d) cells=%d%s %s",
        world_uid,
        tile_gx,
        tile_gy,
        chunk_cx,
        chunk_cy,
        cells,
        job_s,
        _thread_diag(activity=activity),
    )


def log_pack_drain_queue_start(world_uid: str, *, max_jobs: int, pending: int) -> float:
    logger.info(
        "pack drain queue start | world=%s max_jobs=%d pending=%d %s",
        world_uid,
        max_jobs,
        pending,
        _thread_diag(activity="drain_queue_start"),
    )
    return time.perf_counter()


def log_pack_drain_queue_done(world_uid: str, *, processed: int, started_at: float) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "pack drain queue done | world=%s processed=%d elapsed_ms=%.1f",
        world_uid,
        processed,
        elapsed_ms,
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
    logger.debug(
        "pack write %s | world=%s path=%s bytes=%d hash=%s %s %s",
        kind,
        world_uid,
        path,
        nbytes,
        content_hash[:12],
        extra.strip(),
        _thread_diag(activity=f"pack_write_{kind}"),
    )


def log_pack_manifest_saved(world_uid: str, *, content_hash: str | None, l0_tiles: int, l2_chunks: int) -> None:
    logger.info(
        "pack manifest saved | world=%s hash=%s l0_tiles=%d l2_chunks=%d",
        world_uid,
        (content_hash or "")[:12] or "-",
        l0_tiles,
        l2_chunks,
    )


def log_pack_finalize(world_uid: str, *, pack_path: str, content_hash: str | None) -> None:
    logger.info(
        "pack finalize world row | world=%s path=%s hash=%s",
        world_uid,
        pack_path,
        (content_hash or "")[:12] or "-",
    )


def log_pack_bake_done(
    world_uid: str,
    *,
    l0_cells: int,
    chunks_done: int,
    chunks_total: int,
    queue_depth: int,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "pack bake done | world=%s l0_cells=%d chunks=%d/%d queue=%d elapsed_ms=%.1f",
        world_uid,
        l0_cells,
        chunks_done,
        chunks_total,
        queue_depth,
        elapsed_ms,
    )
