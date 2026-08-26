"""Prep contract for FineChunkRunner — explicit, not a closure over refine_rects.

Catalog and heightmap prep are SoT. Discover runs in the worker (R41).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.terrain.relief.discover.timings import (
    GradePipelineTimings,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.pack.refine.detailedGradeCatalog import TileFaceCatalog
from app.application.worldData.pack.refine.meterGradeSurface import Coord
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True, slots=True)
class FineTileContext:
    """Serial prep output. Compute and persist read this; they do not re-load parent/catalog."""

    world: World
    locations: list[NamedLocation]
    surface_ctx: SurfaceTerrainContext
    tile_gx: int
    tile_gy: int
    meter_bbox: ColumnRect
    chunk_size: int
    surface_state: TileSurfaceState
    templates: dict[str, ReliefTemplate]
    grade_halo: int
    existing_uids: dict[Coord, str]
    catalog: TileFaceCatalog
    workers: int
    refine_role: ChunkRefineRole
    phase_name: str
    world_uid: str
    chunks_total: int
    location_pairs: list[tuple[str, TerritoryVolume]]
    volumes: list[TerritoryVolume]


@dataclass(frozen=True, slots=True)
class VertexSlotSeam:
    """T-3c bake fingerprint for one painted vertex slot (not persist-POJO).

    ``grade_uids`` = Instance uids of fronts that painted this slot.
    ``edge_body`` = body cells ``(x, y, z)`` on the owned rect rim (C29 sides).
    Slot is local to the chunk; System uid is not known in the worker.
    `side_parent_slot` is bake-only (same chunk); None unless this slot is a Q2 side
    **and** the slot painted (fingerprint iterates painted uids only).
    """

    slot: int
    grade_uids: tuple[str, ...]
    edge_body: tuple[tuple[int, int, int], ...]
    side_parent_slot: int | None = None


@dataclass(frozen=True, slots=True)
class ChunkComputeResult:
    """One ColumnRect worker output — grade already materialized into cells' surface."""

    chunk_idx: int
    rect: ColumnRect
    cells: list[MapCell]
    chunk_t0: float
    chunk_grades: tuple[ReliefGradeInstance, ...]
    vertex_seams: tuple[VertexSlotSeam, ...] = ()
    rim_rays: tuple[GradeRimRay, ...] = ()
    materialize_s: float = 0.0
    grade_s: float = 0.0
    pipeline_s: GradePipelineTimings = field(default_factory=GradePipelineTimings)
