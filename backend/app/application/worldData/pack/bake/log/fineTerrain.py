"""Fine-terrain refine + detailed bake diagnostics — phases, L2, grade mill."""

from __future__ import annotations

import time

from app.application.worldData.generators.terrain.relief.discover.timings import (
    GradePipelineTimings,
)

from ._shared import _error, _info


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


def log_pack_fine_terrain_phase_done(
    world_uid: str,
    phase: str,
    *,
    chunks_written: int,
    cells_total: int,
    started_at: float,
    pool_workers: int | None = None,
    materialize_s: float = 0.0,
    grade_s: float = 0.0,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack fine_terrain phase done | world=%s phase=%s chunks_written=%d cells=%d "
        "elapsed_s=%.2f materialize_s=%.2f grade_s=%.2f",
        world_uid,
        phase,
        chunks_written,
        cells_total,
        elapsed_s,
        materialize_s,
        grade_s,
        activity="fine_terrain_phase_done",
        world_uid=world_uid,
        phase=phase,
        pool_workers=pool_workers,
        elapsed_s=round(elapsed_s, 2),
        materialize_s=round(materialize_s, 2),
        grade_s=round(grade_s, 2),
    )


def log_pack_l2_formation_done(
    world_uid: str,
    *,
    phase: str,
    chunks: int,
    materialize_s: float,
    grade_s: float,
    l2_s: float,
    tile_gx: int | None = None,
    tile_gy: int | None = None,
    tiles: int | None = None,
    workers: int | None = None,
    grade_persist_s: float | None = None,
    pipeline: GradePipelineTimings | None = None,
) -> None:
    """Wall-clock L2 vs CPU-sum of fill (materialize) and discover+paint (grade).

    ``materialize_s`` / ``grade_s`` are summed across chunks and can exceed ``l2_s``
    when workers > 1. ``l2_s`` is wall of prep + generate + pack persist (not SQL).
    """
    tile_part = (
        f" tile=({tile_gx},{tile_gy})"
        if tile_gx is not None and tile_gy is not None
        else ""
    )
    tiles_part = f" tiles={tiles}" if tiles is not None else ""
    workers_part = f" workers={workers}" if workers is not None else ""
    persist_part = (
        f" grade_persist_s={grade_persist_s:.2f}" if grade_persist_s is not None else ""
    )
    mill_part = pipeline.log_suffix() if pipeline is not None else ""
    mill_fields = pipeline.mill_log_fields() if pipeline is not None else {}
    _info(
        "pack l2 formation done | world=%s phase=%s%s%s chunks=%d%s "
        "materialize_s=%.2f grade_s=%.2f l2_s=%.2f%s%s",
        world_uid,
        phase,
        tile_part,
        tiles_part,
        chunks,
        workers_part,
        materialize_s,
        grade_s,
        l2_s,
        persist_part,
        mill_part,
        activity="l2_formation_done",
        world_uid=world_uid,
        phase=phase,
        chunks=chunks,
        materialize_s=round(materialize_s, 2),
        grade_s=round(grade_s, 2),
        l2_s=round(l2_s, 2),
        tile_gx=tile_gx,
        tile_gy=tile_gy,
        tiles=tiles,
        pool_workers=workers,
        grade_persist_s=(
            round(grade_persist_s, 2) if grade_persist_s is not None else None
        ),
        **mill_fields,
    )


def log_pack_detailed_bake_skip_not_in_index(
    world_uid: str,
    *,
    location_uid: str,
) -> None:
    _error(
        "pack detailed_bake error | world=%s location=%s "
        "not a locations_index pin (occupancy); L2 skipped "
        "reason=not_in_locations_index",
        world_uid,
        location_uid,
        activity="detailed_bake_skip",
        world_uid=world_uid,
        location_uid=location_uid,
        reason="not_in_locations_index",
    )


def log_pack_detailed_bake_start(
    world_uid: str,
    *,
    scope: str,
    grade_mill: bool,
    grade_paint: bool,
) -> None:
    _info(
        "pack detailed_bake start | world=%s scope=%s grade_mill=%s grade_paint=%s",
        world_uid,
        scope,
        grade_mill,
        grade_paint,
        activity="detailed_bake_start",
        world_uid=world_uid,
        scope=scope,
        grade_mill=grade_mill,
        grade_paint=grade_paint,
    )


def log_pack_detailed_bake_done(
    world_uid: str,
    *,
    scope: str,
    tiles: int,
    chunks: int,
    materialize_s: float,
    grade_s: float,
    l2_s: float,
    grade_persist_s: float,
    pipeline: GradePipelineTimings | None = None,
    grade_mill: bool = False,
    grade_paint: bool = False,
) -> None:
    mill_part = pipeline.log_suffix() if pipeline is not None else ""
    mill_fields = pipeline.mill_log_fields() if pipeline is not None else {}
    _info(
        "pack detailed_bake done | world=%s scope=%s tiles=%d chunks=%d "
        "grade_mill=%s grade_paint=%s "
        "materialize_s=%.2f grade_s=%.2f grade_persist_s=%.2f l2_s=%.2f%s",
        world_uid,
        scope,
        tiles,
        chunks,
        grade_mill,
        grade_paint,
        materialize_s,
        grade_s,
        grade_persist_s,
        l2_s,
        mill_part,
        activity="detailed_bake_done",
        world_uid=world_uid,
        scope=scope,
        tiles=tiles,
        chunks=chunks,
        grade_mill=grade_mill,
        grade_paint=grade_paint,
        materialize_s=round(materialize_s, 2),
        grade_s=round(grade_s, 2),
        grade_persist_s=round(grade_persist_s, 2),
        l2_s=round(l2_s, 2),
        **mill_fields,
    )


def log_pack_grade_systems_emit_start(
    world_uid: str,
    *,
    n_instances: int,
) -> float:
    _info(
        "pack grade_systems emit start | world=%s instances=%d",
        world_uid,
        n_instances,
        activity="grade_systems_emit_start",
        world_uid=world_uid,
        n_instances=n_instances,
    )
    return time.perf_counter()


def log_pack_grade_systems_emit_done(
    world_uid: str,
    *,
    n_instances: int,
    n_systems: int,
    started_at: float,
) -> None:
    elapsed_s = time.perf_counter() - started_at
    _info(
        "pack grade_systems emit done | world=%s instances=%d systems=%d "
        "elapsed_s=%.2f elapsed_ms=%.1f",
        world_uid,
        n_instances,
        n_systems,
        elapsed_s,
        elapsed_s * 1000.0,
        activity="grade_systems_emit_done",
        world_uid=world_uid,
        n_instances=n_instances,
        n_systems=n_systems,
        elapsed_s=round(elapsed_s, 2),
        elapsed_ms=elapsed_s * 1000.0,
    )
