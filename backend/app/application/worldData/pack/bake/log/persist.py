"""Pack persist diagnostics — drain, jobs, relief grades, sidecars, blobs."""

from __future__ import annotations

import time

from ._shared import _debug, _info


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


def log_pack_relief_grades_persist_start(
    world_uid: str,
    *,
    n_instances: int,
    n_systems: int,
    replace_world: bool,
) -> float:
    _info(
        "pack relief_grades persist start | world=%s instances=%d systems=%d replace_world=%s",
        world_uid,
        n_instances,
        n_systems,
        replace_world,
        activity="relief_grades_persist_start",
        world_uid=world_uid,
        n_instances=n_instances,
        n_systems=n_systems,
        replace_world=replace_world,
    )
    return time.perf_counter()


def log_pack_relief_grades_persist_progress(
    world_uid: str,
    *,
    kind: str,
    done: int,
    total: int,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack relief_grades persist progress | world=%s kind=%s done=%d/%d elapsed_ms=%.1f",
        world_uid,
        kind,
        done,
        total,
        elapsed_ms,
        activity="relief_grades_persist_progress",
        world_uid=world_uid,
        persist_kind=kind,
        done=done,
        total=total,
        elapsed_ms=elapsed_ms,
    )


def log_pack_relief_grades_persist_done(
    world_uid: str,
    *,
    n_instances: int,
    n_systems: int,
    started_at: float,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack relief_grades persist done | world=%s instances=%d systems=%d "
        "elapsed_s=%.2f elapsed_ms=%.1f",
        world_uid,
        n_instances,
        n_systems,
        elapsed_s,
        elapsed_s * 1000.0,
        activity="relief_grades_persist_done",
        world_uid=world_uid,
        n_instances=n_instances,
        n_systems=n_systems,
        elapsed_s=round(elapsed_s, 2),
        elapsed_ms=elapsed_s * 1000.0,
    )


def log_pack_grade_ray_sidecar_start(world_uid: str, *, n_cells: int) -> float:
    _info(
        "pack grade_ray sidecar start | world=%s cells=%d",
        world_uid,
        n_cells,
        activity="grade_ray_sidecar_start",
        world_uid=world_uid,
        n_cells=n_cells,
    )
    return time.perf_counter()


def log_pack_grade_ray_sidecar_done(
    world_uid: str,
    *,
    n_cells: int,
    started_at: float,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack grade_ray sidecar done | world=%s cells=%d "
        "elapsed_s=%.2f elapsed_ms=%.1f",
        world_uid,
        n_cells,
        elapsed_s,
        elapsed_s * 1000.0,
        activity="grade_ray_sidecar_done",
        world_uid=world_uid,
        n_cells=n_cells,
        elapsed_s=round(elapsed_s, 2),
        elapsed_ms=elapsed_s * 1000.0,
    )


def log_pack_grade_ray_validate_start(world_uid: str, *, n_cells: int) -> float:
    """Heartbeat — persist only if ``DEBUG_GRADE_SLOT_VALIDATE`` is on."""
    _info(
        "pack grade_ray validate start | world=%s cells=%d",
        world_uid,
        n_cells,
        activity="grade_ray_validate_start",
        world_uid=world_uid,
        n_cells=n_cells,
    )
    return time.perf_counter()


def log_pack_grade_ray_validate_progress(
    world_uid: str,
    *,
    done: int,
    total: int,
    empty: int,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack grade_ray validate progress | world=%s done=%d/%d empty=%d elapsed_ms=%.1f",
        world_uid,
        done,
        total,
        empty,
        elapsed_ms,
        activity="grade_ray_validate_progress",
        world_uid=world_uid,
        done=done,
        total=total,
        empty=empty,
        elapsed_ms=elapsed_ms,
    )


def log_pack_grade_ray_validate_done(
    world_uid: str,
    *,
    n_cells: int,
    empty: int,
    started_at: float,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack grade_ray validate done | world=%s cells=%d empty=%d "
        "elapsed_s=%.2f elapsed_ms=%.1f",
        world_uid,
        n_cells,
        empty,
        elapsed_s,
        elapsed_s * 1000.0,
        activity="grade_ray_validate_done",
        world_uid=world_uid,
        n_cells=n_cells,
        empty=empty,
        elapsed_s=round(elapsed_s, 2),
        elapsed_ms=elapsed_s * 1000.0,
    )
