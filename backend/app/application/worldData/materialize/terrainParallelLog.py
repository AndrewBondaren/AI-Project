"""Diagnostics for TR-PAR terrain chunk workers — thread and CPU core logging."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.worldData.generators.terrain.types import ColumnRect

logger = logging.getLogger(__name__)


def current_cpu_core() -> int | None:
    """Best-effort logical CPU index for the running thread (OS may migrate)."""
    if sys.platform == "win32":
        try:
            import ctypes
            fn = getattr(ctypes.windll.kernel32, "GetCurrentProcessorNumber", None)
            if fn is not None:
                return int(fn())
        except (OSError, AttributeError, ValueError):
            return None
    try:
        return int(os.sched_getcpu())  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        return None


def _rect_label(rect: ColumnRect) -> str:
    return f"x={rect.x_min}..{rect.x_max} y={rect.y_min}..{rect.y_max}"


def log_terrain_tile_start(
    world_uid: str,
    tile_gx: int,
    tile_gy: int,
    *,
    workers: int,
    chunks_total: int,
) -> None:
    logger.info(
        "terrain materialize | world=%s tile=(%d,%d) workers=%d chunks_total=%d",
        world_uid, tile_gx, tile_gy, workers, chunks_total,
    )


def log_terrain_chunk_generate_start(
    world_uid: str,
    chunk_idx: int,
    chunks_total: int,
    *,
    workers: int,
    rect: ColumnRect,
) -> float:
    cpu = current_cpu_core()
    logger.info(
        "terrain chunk generate start | world=%s chunk=%d/%d pool_workers=%d "
        "thread=%s tid=%s cpu=%s rect=%s",
        world_uid,
        chunk_idx + 1,
        chunks_total,
        workers,
        threading.current_thread().name,
        threading.get_ident(),
        cpu if cpu is not None else "?",
        _rect_label(rect),
    )
    return time.perf_counter()


def log_terrain_chunk_generate_done(
    world_uid: str,
    chunk_idx: int,
    chunks_total: int,
    *,
    workers: int,
    rect: ColumnRect,
    cell_count: int,
    started_at: float,
) -> None:
    cpu = current_cpu_core()
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "terrain chunk generate done | world=%s chunk=%d/%d pool_workers=%d "
        "thread=%s tid=%s cpu=%s rect=%s cells=%d elapsed_ms=%.1f",
        world_uid,
        chunk_idx + 1,
        chunks_total,
        workers,
        threading.current_thread().name,
        threading.get_ident(),
        cpu if cpu is not None else "?",
        _rect_label(rect),
        cell_count,
        elapsed_ms,
    )


def log_terrain_chunk_persist(
    world_uid: str,
    chunk_idx: int,
    chunks_total: int,
    *,
    workers: int,
    rect: ColumnRect,
    cell_count: int,
    upserted: int,
    elapsed_ms: float,
) -> None:
    cpu = current_cpu_core()
    logger.info(
        "terrain chunk persist | world=%s chunk=%d/%d pool_workers=%d "
        "thread=%s tid=%s cpu=%s rect=%s cells=%d upserted=%d elapsed_ms=%.1f",
        world_uid,
        chunk_idx + 1,
        chunks_total,
        workers,
        threading.current_thread().name,
        threading.get_ident(),
        cpu if cpu is not None else "?",
        _rect_label(rect),
        cell_count,
        upserted,
        elapsed_ms,
    )
