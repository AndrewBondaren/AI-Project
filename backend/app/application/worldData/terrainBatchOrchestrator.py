"""Terrain surface helpers for pack L2 refine — parent-light upsample + chunk generate.

Legacy map_cells ``save_terrain_batch`` / ``_materialize_fine_tile`` removed.
Pack L0 bake + fine refine own persist via ``WorldPackWriter``.

See ``docs/tz_terrain_generation.md`` § multi-pass skeleton; WP-PERF-22 Parent light SoT.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.api.schemas.imports import ImportResult
from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
    prepare_surface_terrain_context,
)
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.mapCellService import MapCellService
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TileSurfaceState:
    heightmap: object
    n_eff: object
    hydrology: dict | None


class TerrainBatchOrchestrator:
    """Pack L2 surface state + chunk generate; bootstrap tile planning for L0 bake."""

    def __init__(
        self,
        map_cell_service: MapCellService,
        generator: TerrainGeneratorService | None = None,
    ) -> None:
        self._map_cells = map_cell_service
        self._generator = generator or TerrainGeneratorService()

    def plan_bootstrap_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        max_tiles: int | None = None,
    ) -> list[tuple[int, int]]:
        from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner

        ctx = prepare_surface_terrain_context(
            world,
            locations,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if ctx is None:
            return []
        plan = PackTilePlanner().plan(
            world, locations, ctx, scope="light", max_tiles=max_tiles,
        )
        return plan.tile_tuples()

    async def save_z_slice(
        self,
        world: World,
        locations: list[NamedLocation],
        gx: int,
        gy: int,
        z_lo: int,
        z_hi: int,
    ) -> ImportResult:
        pole_field = run_pole_resolve_pass(world, locations)
        cells = self._generator.generate_z_slice(
            world, locations, pole_field, gx, gy, z_lo, z_hi,
        )
        return await self._map_cells.save_pass(cells, "terrain")

    def build_tile_surface_state(
        self,
        world: World,
        locations: list[NamedLocation],
        ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        *,
        parent_light: ParentLightTile,
        refine_policy: ParentLightRefinePolicy | None = None,
    ) -> TileSurfaceState:
        """L2 surface from baked L0 parent light (WP-PERF-22) — not coarse stamp."""
        from app.application.worldData.generators.hydrology.shore.parentLightHydroCorridor import (
            merge_hydro_hard_corridor,
        )
        from app.application.worldData.generators.terrain.passes.parentLightUpsample import (
            meter_bbox_for_parent,
            upsample_from_parent_light,
        )
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap

        if parent_light.gx != tile_gx or parent_light.gy != tile_gy:
            raise ValueError(
                f"parent_light tile mismatch: got ({parent_light.gx},{parent_light.gy}) "
                f"expected ({tile_gx},{tile_gy})",
            )

        policy = refine_policy or ParentLightRefinePolicy.canonical_defaults()
        fine_z = upsample_from_parent_light(parent_light, world, policy=policy)
        cell_m = parent_light.tile_m
        for (xm, ym), z in ctx.meter_z_overrides.items():
            if xm // cell_m == tile_gx and ym // cell_m == tile_gy:
                base = fine_z.get((xm, ym), z)
                lo = base - policy.z_band
                hi = base + policy.z_band
                fine_z[(xm, ym)] = max(lo, min(hi, int(z)))

        meter_bbox = meter_bbox_for_parent(parent_light)
        heightmap = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=meter_bbox,
            surface_z=fine_z,
        )
        tile_hydro = merge_hydro_hard_corridor(parent_light, ctx.sparse_meter_hydro)
        n_eff = run_gap_analysis(world, heightmap)
        return TileSurfaceState(heightmap=heightmap, n_eff=n_eff, hydrology=tile_hydro or None)

    async def generate_chunk_cells(
        self,
        world: World,
        locations: list[NamedLocation],
        ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        rect: ColumnRect,
        *,
        surface_state: TileSurfaceState | None = None,
        parent_light: ParentLightTile | None = None,
    ) -> list[MapCell]:
        return self.generate_chunk_cells_sync(
            world, locations, ctx, tile_gx, tile_gy, rect,
            surface_state=surface_state,
            parent_light=parent_light,
        )

    def generate_chunk_cells_sync(
        self,
        world: World,
        locations: list[NamedLocation],
        ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        rect: ColumnRect,
        *,
        surface_state: TileSurfaceState | None = None,
        parent_light: ParentLightTile | None = None,
    ) -> list[MapCell]:
        if surface_state is None:
            if parent_light is None:
                raise ValueError(
                    "parent_light or surface_state required for L2 generate (WP-PERF-22)",
                )
            surface_state = self.build_tile_surface_state(
                world, locations, ctx, tile_gx, tile_gy, parent_light=parent_light,
            )
        return self._generator.generate_surface_chunk(
            world,
            locations,
            surface_state.heightmap,
            surface_state.n_eff,
            rect,
            hydrology_by_cell=surface_state.hydrology,
        )
