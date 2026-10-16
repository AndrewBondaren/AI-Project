"""World-map bake diagnostics — surface context, sampling gaps, flat tiles."""

from __future__ import annotations

import time

from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole

from ._shared import _diag_extra, _info, logger

# Hist bucket when ``system_terrain`` is missing on the wire — not a registry key.
MISSING_SYSTEM_TERRAIN = "?"


def terrain_hist_is_only_plains(terrain_hist: dict[str, int] | None) -> bool:
    if terrain_hist is None:
        return False
    plains = WorldTerrainMasks.canonical_defaults().default_plains.system_terrain
    return set(terrain_hist) <= {plains, MISSING_SYSTEM_TERRAIN}


def hydro_hist_is_only_none(hydro_hist: dict[str, int] | None) -> bool:
    if hydro_hist is None:
        return False
    return set(hydro_hist) <= {WorldMapHydrologyRole.NONE.name}


def log_pack_surface_context(
    world_uid: str,
    *,
    ok: bool,
    started_at: float,
    coarse_surface_z_n: int | None = None,
    coarse_hydro_n: int | None = None,
    sparse_fine_hydro_n: int | None = None,
    fine_z_overrides_n: int | None = None,
    hydrology_enabled: bool | None = None,
    hydro_role_hist: dict[str, int] | None = None,
    surface_z_hist: dict[str, int] | None = None,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack surface context | world=%s ok=%s elapsed_ms=%.1f "
        "coarse_z=%s coarse_hydro=%s sparse_fine_hydro=%s fine_z_overrides=%s "
        "hydrology_enabled=%s hydro_roles=%s surface_z_hist=%s",
        world_uid,
        ok,
        elapsed_ms,
        coarse_surface_z_n if coarse_surface_z_n is not None else "-",
        coarse_hydro_n if coarse_hydro_n is not None else "-",
        sparse_fine_hydro_n if sparse_fine_hydro_n is not None else "-",
        fine_z_overrides_n if fine_z_overrides_n is not None else "-",
        hydrology_enabled if hydrology_enabled is not None else "-",
        hydro_role_hist if hydro_role_hist is not None else "-",
        surface_z_hist if surface_z_hist is not None else "-",
        activity="surface_context_prepare",
        world_uid=world_uid,
        coarse_surface_z_n=coarse_surface_z_n,
        coarse_hydro_n=coarse_hydro_n,
        sparse_fine_hydro_n=sparse_fine_hydro_n,
    )
    if ok and hydrology_enabled and (coarse_hydro_n or 0) == 0:
        logger.warning(
            "pack surface context | world=%s hydrology enabled but coarse_hydro empty",
            world_uid,
            extra=_diag_extra(
                activity="surface_context_hydro_empty",
                world_uid=world_uid,
            ),
        )


def log_pack_world_map_sampling_note(
    world_uid: str,
    *,
    sparse_fine_hydro_n: int,
    fine_z_overrides_n: int,
) -> None:
    """Warn when meter-resolution hydro/z exists but light bake samples macro keys only."""
    if sparse_fine_hydro_n <= 0 and fine_z_overrides_n <= 0:
        return
    logger.warning(
        "pack world_map sampling | world=%s light cells use macro (gx,gy) for "
        "surface_z/hydro; sparse_fine_hydro=%d fine_z_overrides=%d are NOT applied "
        "per (tx,ty) — expect flat tiles / missing rivers on light map",
        world_uid,
        sparse_fine_hydro_n,
        fine_z_overrides_n,
        extra=_diag_extra(
            activity="world_map_sampling_gap",
            world_uid=world_uid,
            sparse_fine_hydro_n=sparse_fine_hydro_n,
            fine_z_overrides_n=fine_z_overrides_n,
        ),
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
    tile_uid: str,
    terrain_hist: dict[str, int] | None = None,
    hydro_hist: dict[str, int] | None = None,
    surface_z_hist: dict[str, int] | None = None,
    macro_hydro_role: str | None = None,
    macro_surface_z: int | None = None,
) -> None:
    _info(
        "pack world_map tile done | world=%s tile=%d/%d gx=%d gy=%d tile_uid=%s "
        "cells=%d hash=%s elapsed_ms=%.1f terrain=%s hydro=%s z=%s "
        "macro_hydro=%s macro_z=%s",
        world_uid,
        tile_idx,
        tiles_total,
        gx,
        gy,
        tile_uid,
        cells,
        (content_hash or "")[:12] or "-",
        elapsed_ms,
        terrain_hist if terrain_hist is not None else "-",
        hydro_hist if hydro_hist is not None else "-",
        surface_z_hist if surface_z_hist is not None else "-",
        macro_hydro_role if macro_hydro_role is not None else "-",
        macro_surface_z if macro_surface_z is not None else "-",
        activity="world_map_tile_write",
        world_uid=world_uid,
        tile_gx=gx,
        tile_gy=gy,
        tile_uid=tile_uid,
        terrain_hist=terrain_hist,
        hydro_hist=hydro_hist,
    )
    only_plains = terrain_hist_is_only_plains(terrain_hist)
    only_none_hydro = hydro_hist_is_only_none(hydro_hist)
    if cells > 0 and only_plains and only_none_hydro:
        logger.warning(
            "pack world_map tile flat | world=%s gx=%d gy=%d all plains+NONE "
            "(macro_hydro=%s macro_z=%s) — check coarse_hydro keying / surface_z→terrain",
            world_uid,
            gx,
            gy,
            macro_hydro_role,
            macro_surface_z,
            extra=_diag_extra(
                activity="world_map_tile_flat",
                world_uid=world_uid,
                tile_gx=gx,
                tile_gy=gy,
            ),
        )


def log_pack_world_map_bake_done(
    world_uid: str,
    *,
    total_cells: int,
    tiles: int,
    started_at: float,
    terrain_hist: dict[str, int] | None = None,
    hydro_hist: dict[str, int] | None = None,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    _info(
        "pack world_map bake done | world=%s tiles=%d world_map_cells=%d "
        "elapsed_ms=%.1f terrain=%s hydro=%s",
        world_uid,
        tiles,
        total_cells,
        elapsed_ms,
        terrain_hist if terrain_hist is not None else "-",
        hydro_hist if hydro_hist is not None else "-",
        activity="world_map_bake_done",
        world_uid=world_uid,
        total_cells=total_cells,
        terrain_hist=terrain_hist,
        hydro_hist=hydro_hist,
    )
    only_plains = terrain_hist_is_only_plains(terrain_hist)
    only_none_hydro = hydro_hist_is_only_none(hydro_hist)
    if total_cells > 0 and only_plains and only_none_hydro:
        logger.warning(
            "pack world_map bake all-flat | world=%s cells=%d — light map has no "
            "hydro/terrain variety (same symptom as ASCII all '.')",
            world_uid,
            total_cells,
            extra=_diag_extra(
                activity="world_map_bake_all_flat",
                world_uid=world_uid,
                total_cells=total_cells,
            ),
        )
