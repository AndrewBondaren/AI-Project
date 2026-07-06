"""Caller contract for world surface materialization (terrain + climate).

DAG nodes and debug HTTP routes pass ``MaterializationContext`` into batch
orchestrators. Generators do not probe CPU counts.

See ``docs/tz_terrain_generation.md`` § TR-PAR, ``architecture-first.mdc``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.api.schemas.imports import ImportResult
from app.db.models.world import World

# Until DAG passes probe: debug HTTP uses this when query param omitted.
DEBUG_FREE_CORES_STUB = 5


@dataclass(frozen=True)
class MaterializationContext:
    """Immutable input from caller — orchestrators derive worker counts via ParallelPolicy."""

    free_cores: int
    parallel_workers_override: int | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class MaterializationJobReport:
    """Aggregated result for surface stack (S→CL)."""

    terrain: ImportResult
    climate: ImportResult | None
    chunks_total: int
    chunks_done: int
    terrain_workers: int
    climate_workers: int

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
        return payload


def resolve_materialization_context(
    world: World,
    *,
    free_cores: int | None = None,
    parallel_workers_override: int | None = None,
    job_id: str | None = None,
) -> MaterializationContext:
    """Build context for debug routes; DAG supplies probed ``free_cores`` later."""
    _ = world  # reserved for per-world caller policy extensions
    cores = free_cores if free_cores is not None else DEBUG_FREE_CORES_STUB
    return MaterializationContext(
        free_cores=max(1, cores),
        parallel_workers_override=parallel_workers_override,
        job_id=job_id,
    )
