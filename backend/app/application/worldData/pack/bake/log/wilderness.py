"""Wilderness chunk refine diagnostics — generate / persist / done."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ._shared import _info

if TYPE_CHECKING:
    from app.application.worldData.generators.terrain.types import ColumnRect


def _rect_label(rect: ColumnRect) -> str:
    return f"x={rect.x_min}..{rect.x_max} y={rect.y_min}..{rect.y_max}"


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
