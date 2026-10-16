"""Diagnostics for World Pack bake / fine-terrain refine — mirrors terrainParallelLog.

Per-world bake file (survive terminal scrollback)::

    logs/generation/{world_uid}/bake-light-latest.log

Attached for the duration of ``PackMaterializationOrchestrator.materialize_light_pack``
via ``app.core.generationLogging.generation_world_log``.

Split by bake phase into sibling modules; this package re-exports the full
public surface. Callers keep the historical import point through the
``packBakeLog`` facade module.
"""

from .climate import (
    log_pack_climate_batch_done,
    log_pack_climate_batch_start,
    log_pack_climate_coarse_done,
    log_pack_climate_tile_done,
)
from .compute import log_pack_compute_pool
from .fineTerrain import (
    log_pack_detailed_bake_done,
    log_pack_detailed_bake_skip_not_in_index,
    log_pack_detailed_bake_start,
    log_pack_fine_terrain_phase_done,
    log_pack_fine_terrain_phase_start,
    log_pack_fine_terrain_workers,
    log_pack_grade_systems_emit_done,
    log_pack_grade_systems_emit_start,
    log_pack_l2_formation_done,
)
from .misc import (
    log_pack_bake_done,
    log_pack_bake_start,
    log_pack_drain_queue_done,
    log_pack_drain_queue_start,
    log_pack_entry_anchor_fallback,
    log_pack_loading_progress,
    log_pack_queue_enqueue,
    log_pack_queue_scheduled,
    log_pack_worker_chunk,
)
from .persist import (
    log_pack_drain_persisted_done,
    log_pack_drain_persisted_start,
    log_pack_finalize,
    log_pack_grade_ray_sidecar_done,
    log_pack_grade_ray_sidecar_start,
    log_pack_grade_ray_validate_done,
    log_pack_grade_ray_validate_progress,
    log_pack_grade_ray_validate_start,
    log_pack_jobs_persisted,
    log_pack_location_terrain_persist,
    log_pack_manifest_saved,
    log_pack_relief_grades_persist_done,
    log_pack_relief_grades_persist_progress,
    log_pack_relief_grades_persist_start,
    log_pack_write_blob,
)
from .settlement import (
    log_pack_settlement_c11_done,
    log_pack_settlement_c11_start,
    log_pack_settlement_skip_not_in_index,
    log_pack_settlement_topology_batch_done,
    log_pack_settlement_topology_batch_start,
    log_pack_settlement_topology_done,
    log_pack_settlement_topology_start,
)
from .wilderness import (
    log_pack_wilderness_chunk_done,
    log_pack_wilderness_chunk_persist,
    log_pack_wilderness_chunk_start,
)
from .worldMap import (
    MISSING_SYSTEM_TERRAIN,
    hydro_hist_is_only_none,
    log_pack_surface_context,
    log_pack_world_map_bake_done,
    log_pack_world_map_bake_start,
    log_pack_world_map_sampling_note,
    log_pack_world_map_tile_done,
    terrain_hist_is_only_plains,
)

__all__ = [
    "MISSING_SYSTEM_TERRAIN",
    "hydro_hist_is_only_none",
    "log_pack_bake_done",
    "log_pack_bake_start",
    "log_pack_climate_batch_done",
    "log_pack_climate_batch_start",
    "log_pack_climate_coarse_done",
    "log_pack_climate_tile_done",
    "log_pack_compute_pool",
    "log_pack_detailed_bake_done",
    "log_pack_detailed_bake_skip_not_in_index",
    "log_pack_detailed_bake_start",
    "log_pack_drain_persisted_done",
    "log_pack_drain_persisted_start",
    "log_pack_drain_queue_done",
    "log_pack_drain_queue_start",
    "log_pack_entry_anchor_fallback",
    "log_pack_finalize",
    "log_pack_fine_terrain_phase_done",
    "log_pack_fine_terrain_phase_start",
    "log_pack_fine_terrain_workers",
    "log_pack_grade_ray_sidecar_done",
    "log_pack_grade_ray_sidecar_start",
    "log_pack_grade_ray_validate_done",
    "log_pack_grade_ray_validate_progress",
    "log_pack_grade_ray_validate_start",
    "log_pack_grade_systems_emit_done",
    "log_pack_grade_systems_emit_start",
    "log_pack_jobs_persisted",
    "log_pack_l2_formation_done",
    "log_pack_loading_progress",
    "log_pack_location_terrain_persist",
    "log_pack_manifest_saved",
    "log_pack_queue_enqueue",
    "log_pack_queue_scheduled",
    "log_pack_relief_grades_persist_done",
    "log_pack_relief_grades_persist_progress",
    "log_pack_relief_grades_persist_start",
    "log_pack_settlement_c11_done",
    "log_pack_settlement_c11_start",
    "log_pack_settlement_skip_not_in_index",
    "log_pack_settlement_topology_batch_done",
    "log_pack_settlement_topology_batch_start",
    "log_pack_settlement_topology_done",
    "log_pack_settlement_topology_start",
    "log_pack_surface_context",
    "log_pack_wilderness_chunk_done",
    "log_pack_wilderness_chunk_persist",
    "log_pack_wilderness_chunk_start",
    "log_pack_worker_chunk",
    "log_pack_world_map_bake_done",
    "log_pack_world_map_bake_start",
    "log_pack_world_map_sampling_note",
    "log_pack_world_map_tile_done",
    "log_pack_write_blob",
    "terrain_hist_is_only_plains",
]
