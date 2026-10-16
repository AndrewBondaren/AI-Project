"""Caller contract for world surface materialization (terrain + climate).

DAG nodes and debug HTTP routes pass ``MaterializationContext`` into batch
orchestrators. Generators do not probe CPU counts.

See ``docs/tz_terrain_generation.md`` § TR-PAR, ``architecture-first.mdc``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.worldData.persistResult import PersistResult
from app.db.models.world import World

# Until DAG passes probe: debug HTTP uses this when query param omitted.
DEBUG_FREE_CORES_STUB = 5
DEFAULT_CHUNKS_PER_COMMIT = 8


def persist_result_from_import(result) -> PersistResult:
    """Bridge legacy terrain/climate batch counters until those paths migrate."""
    return PersistResult(
        total=result.total,
        succeeded=result.succeeded,
        failed=result.failed,
    )


@dataclass(frozen=True)
class MaterializationContext:
    """Immutable input from caller — orchestrators derive worker counts via ParallelPolicy.

    Backlog: split caller vs persist policy — ``docs/tz_terrain_generation.md`` § TR-PERF-DEBT-1.
    """

    free_cores: int
    parallel_workers_override: int | None = None
    job_id: str | None = None
    chunks_per_commit: int = DEFAULT_CHUNKS_PER_COMMIT
    insert_only: bool | None = None  # None → auto; guard gap § TR-PERF-DEBT-3
    bulk_write_pragmas: bool = True


@dataclass(frozen=True)
class MaterializationJobReport:
    """Aggregated result for surface stack (S→CL)."""

    terrain: PersistResult
    climate: PersistResult | None
    chunks_total: int
    chunks_done: int
    terrain_workers: int
    climate_workers: int
    elapsed_s: float | None = None
    world_map_cells: int | None = None
    refine_queue_depth: int | None = None
    climate_coarse_samples: int | None = None
    climate_fine_tiles: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "terrain": self.terrain.to_dict(),
            "chunks_total": self.chunks_total,
            "chunks_done": self.chunks_done,
            "terrain_workers": self.terrain_workers,
            "climate_workers": self.climate_workers,
        }
        if self.climate is not None:
            payload["climate"] = self.climate.to_dict()
        if self.elapsed_s is not None:
            payload["elapsed_s"] = round(self.elapsed_s, 2)
        if self.world_map_cells is not None:
            payload["world_map_cells"] = self.world_map_cells
        if self.refine_queue_depth is not None:
            payload["refine_queue_depth"] = self.refine_queue_depth
        if self.climate_coarse_samples is not None:
            payload["climate_coarse_samples"] = self.climate_coarse_samples
        if self.climate_fine_tiles is not None:
            payload["climate_fine_tiles"] = self.climate_fine_tiles
        return payload


def resolve_materialization_context(
    world: World,
    *,
    free_cores: int | None = None,
    parallel_workers_override: int | None = None,
    job_id: str | None = None,
    chunks_per_commit: int | None = None,
    insert_only: bool | None = None,
    bulk_write_pragmas: bool = True,
) -> MaterializationContext:
    """Build context for debug routes; DAG supplies probed ``free_cores`` later."""
    _ = world  # reserved for per-world caller policy extensions
    cores = free_cores if free_cores is not None else DEBUG_FREE_CORES_STUB
    cpc = chunks_per_commit if chunks_per_commit is not None else DEFAULT_CHUNKS_PER_COMMIT
    return MaterializationContext(
        free_cores=max(1, cores),
        parallel_workers_override=parallel_workers_override,
        job_id=job_id,
        chunks_per_commit=max(1, cpc),
        insert_only=insert_only,
        bulk_write_pragmas=bulk_write_pragmas,
    )


def resolve_insert_only(
    ctx: MaterializationContext,
    *,
    world_has_cells: bool,
) -> MaterializationContext:
    """TR-PERF-3: auto-detect insert fast path when caller did not set ``insert_only``."""
    if ctx.insert_only is not None:
        return ctx
    return replace(ctx, insert_only=not world_has_cells)
