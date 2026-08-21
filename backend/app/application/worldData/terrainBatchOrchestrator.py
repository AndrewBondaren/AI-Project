"""Terrain surface helpers for pack L2 refine — parent-light upsample + chunk generate.

Legacy map_cells ``save_terrain_batch`` / ``_materialize_fine_tile`` removed.
Pack L0 bake + fine refine own persist via ``WorldPackWriter``.

See ``docs/tz_terrain_generation.md`` § multi-pass skeleton; WP-PERF-22 Parent light SoT.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

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
from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.application.worldData.mapCellService import MapCellService
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.facing import Facing
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
    heightmap: SurfaceHeightmap
    n_eff: dict[tuple[int, int], int]
    hydrology: dict[tuple[int, int], MapCellHydrology] | None
    surface_terrain: dict[tuple[int, int], str] | None = None
    surface_facing: dict[tuple[int, int], Facing] | None = None
    surface_grade_uid: dict[tuple[int, int], str] | None = None


def refresh_tile_gaps(world: World, state: TileSurfaceState) -> TileSurfaceState:
    """Recompute ``n_eff`` after halo meters were merged into the heightmap."""
    return replace(state, n_eff=run_gap_analysis(world, state.heightmap))


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
        """L2 surface: upsample + terrain carry + hills + hydro + gap (before chunk pool)."""
        from app.application.jsonValidation import terrain_masks
        from app.application.worldData.generators.climate.math import world_seed
        from app.application.worldData.generators.hydrology.shore.parentLightHydroCorridor import (
            hydro_mask_from_parent,
            merge_hydro_hard_corridor,
        )
        from app.application.worldData.generators.terrain.hills import place_hills
        from app.application.worldData.generators.terrain.passes.parentLightTerrain import (
            upsample_facing_from_parent_light,
            upsample_terrain_from_parent_light,
        )
        from app.application.worldData.generators.terrain.passes.parentLightUpsample import (
            meter_bbox_for_parent,
            upsample_from_parent_light,
        )
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap
        from app.application.worldData.generators.terrain.worldMapSettings import (
            world_z_max,
            world_z_min,
        )

        if parent_light.gx != tile_gx or parent_light.gy != tile_gy:
            raise ValueError(
                f"parent_light tile mismatch: got ({parent_light.gx},{parent_light.gy}) "
                f"expected ({tile_gx},{tile_gy})",
            )

        policy = refine_policy or ParentLightRefinePolicy.canonical_defaults()
        fine_z = upsample_from_parent_light(parent_light, world, policy=policy)
        fine_terrain = upsample_terrain_from_parent_light(parent_light, world, policy=policy)
        fine_facing = upsample_facing_from_parent_light(parent_light, policy=policy)
        cell_m = parent_light.tile_m
        for (xm, ym), z in ctx.meter_z_overrides.items():
            if xm // cell_m == tile_gx and ym // cell_m == tile_gy:
                base = fine_z.get((xm, ym), z)
                lo = base - policy.z_band
                hi = base + policy.z_band
                fine_z[(xm, ym)] = max(lo, min(hi, int(z)))

        l0_hydro = hydro_mask_from_parent(parent_light)
        masks = terrain_masks(world)
        place_hills(
            fine_z,
            fine_terrain,
            l0_hydro,
            plains_key=masks.default_plains.system_terrain,
            forest_key=masks.default_forests.system_terrain,
            plains_hills=masks.default_plains.hills,
            forest_hills=masks.default_forests.hills,
            seed=world_seed(world),
            z_min=world_z_min(world),
            z_max=world_z_max(world),
        )

        meter_bbox = meter_bbox_for_parent(parent_light)
        heightmap = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=meter_bbox,
            surface_z=fine_z,
        )
        tile_hydro = merge_hydro_hard_corridor(parent_light, ctx.sparse_meter_hydro)
        n_eff = run_gap_analysis(world, heightmap)
        return TileSurfaceState(
            heightmap=heightmap,
            n_eff=n_eff,
            hydrology=tile_hydro or None,
            surface_terrain=fine_terrain,
            surface_facing=fine_facing or None,
            surface_grade_uid=None,
        )

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
            surface_terrain=surface_state.surface_terrain,
            surface_facing=surface_state.surface_facing,
            surface_grade_uid=surface_state.surface_grade_uid,
        )
