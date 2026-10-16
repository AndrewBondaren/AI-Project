"""Climate bake diagnostics — batch CPU/thread sampling, coarse/tile done."""

from __future__ import annotations

import threading
import time

from app.application.worldData.materialize.terrainParallelLog import current_cpu_core

from ._shared import _debug, _info


def _climate_tile_part(tile_gx: int | None, tile_gy: int | None) -> str:
    if tile_gx is None or tile_gy is None:
        return ""
    return f" tile=({tile_gx},{tile_gy})"


def log_pack_climate_batch_start(
    world_uid: str,
    *,
    phase: str,
    batch: int,
    batches_total: int,
    workers: int,
    samples: int,
    tile_gx: int | None = None,
    tile_gy: int | None = None,
) -> float:
    """DEBUG: which thread / logical CPU is sampling a climate row batch."""
    cpu = current_cpu_core()
    thread = threading.current_thread()
    _debug(
        "pack climate batch start | world=%s phase=%s batch=%d/%d pool_workers=%d "
        "thread=%s tid=%s cpu=%s samples=%d%s",
        world_uid,
        phase,
        batch,
        batches_total,
        workers,
        thread.name,
        thread.ident,
        cpu if cpu is not None else "?",
        samples,
        _climate_tile_part(tile_gx, tile_gy),
        activity="climate_batch",
        pool_workers=workers,
        world_uid=world_uid,
        phase=phase,
        batch=batch,
        batches_total=batches_total,
        samples=samples,
        tile_gx=tile_gx,
        tile_gy=tile_gy,
    )
    return time.perf_counter()


def log_pack_climate_batch_done(
    world_uid: str,
    *,
    phase: str,
    batch: int,
    batches_total: int,
    workers: int,
    samples: int,
    started_at: float,
    tile_gx: int | None = None,
    tile_gy: int | None = None,
) -> None:
    cpu = current_cpu_core()
    thread = threading.current_thread()
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _debug(
        "pack climate batch done | world=%s phase=%s batch=%d/%d pool_workers=%d "
        "thread=%s tid=%s cpu=%s samples=%d elapsed_ms=%.1f%s",
        world_uid,
        phase,
        batch,
        batches_total,
        workers,
        thread.name,
        thread.ident,
        cpu if cpu is not None else "?",
        samples,
        elapsed_ms,
        _climate_tile_part(tile_gx, tile_gy),
        activity="climate_batch",
        pool_workers=workers,
        world_uid=world_uid,
        phase=phase,
        batch=batch,
        batches_total=batches_total,
        samples=samples,
        elapsed_ms=round(elapsed_ms, 1),
        tile_gx=tile_gx,
        tile_gy=tile_gy,
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
