"""Pack L2 surface helpers — parent-light upsample + chunk generate.

Pack L0 bake + fine refine own persist via ``WorldPackWriter``.

See ``docs/tz_terrain_generation.md`` § multi-pass skeleton; WP-PERF-22 Parent light SoT.
"""

from __future__ import annotations
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from collections.abc import Mapping
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry

import logging
from dataclasses import dataclass, replace

from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService
from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.facing import Facing
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
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
    surface_region_uid: dict[tuple[int, int], str] | None = None


def refresh_tile_gaps(world: World, state: TileSurfaceState) -> TileSurfaceState:
    """Recompute ``n_eff`` after halo fine cells were merged into the heightmap."""
    return replace(state, n_eff=run_gap_analysis(world, state.heightmap))


class TerrainBatchOrchestrator:
    """Pack L2 surface state + chunk generate."""

    def __init__(self, generator: TerrainGeneratorService | None = None) -> None:
        self._generator = generator or TerrainGeneratorService()

    def build_tile_surface_state(
        self,
        world: World,
        locations: list[NamedLocation],
        bundle: SurfacePlanBundle,
        tile_gx: int,
        tile_gy: int,
        *,
        parent_light: ParentLightTile,
        refine_policy: ParentLightRefinePolicy | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> TileSurfaceState:
        """L2 surface: upsample + terrain carry + hills + hydro + gap (before chunk pool)."""
        from app.application.jsonValidation.terrainHillRegistry import terrain_with_hills
        from app.application.worldData.generators.climate.math import world_seed
        from app.application.worldData.generators.hydrology.shore.parentLightHydroCorridor import (
            hydro_mask_from_parent,
            merge_hydro_hard_corridor,
        )
        from app.application.worldData.generators.terrain.hills import place_hills
        from app.application.worldData.generators.terrain.landcover.finePaint import (
            paint_regions_fine,
        )
        from app.application.worldData.generators.terrain.passes.parentLightTerrain import (
            upsample_facing_from_parent_light,
            upsample_terrain_from_parent_light,
        )
        from app.application.worldData.generators.terrain.passes.parentLightUpsample import (
            fine_bbox_for_parent,
            upsample_from_parent_light,
        )
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap
        from app.application.worldData.generators.terrain.worldMapSettings import (
            world_z_max,
            world_z_min,
        )

        if bundle.world_uid != world.world_uid:
            raise ValueError("surface bundle belongs to another world")
        if parent_light.gx != tile_gx or parent_light.gy != tile_gy:
            raise ValueError(
                f"parent_light tile mismatch: got ({parent_light.gx},{parent_light.gy}) "
                f"expected ({tile_gx},{tile_gy})",
            )

        policy = refine_policy or ParentLightRefinePolicy.canonical_defaults()
        fine_z = upsample_from_parent_light(parent_light, world, policy=policy)
        fine_terrain = upsample_terrain_from_parent_light(parent_light, world, policy=policy)
        fine_facing = upsample_facing_from_parent_light(parent_light, policy=policy)
        for (xm, ym), z in working.hydrology.fine_z_for_tile(GridX(tile_gx), GridY(tile_gy)).items():
            base = fine_z.get((xm, ym), z)
            lo = base - policy.z_band
            hi = base + policy.z_band
            fine_z[(xm, ym)] = max(lo, min(hi, int(z)))

        fine_bbox = fine_bbox_for_parent(parent_light)
        l0_hydro = hydro_mask_from_parent(parent_light)
        # L0 carry is the background only; regions paint pointwise in fine cells.
        fine_region_uid = paint_regions_fine(
            world,
            locations,
            bundle,
            parent_light,
            fine_terrain=fine_terrain,
            l0_hydro=l0_hydro,
            tile_bbox=(fine_bbox.x_min, fine_bbox.y_min, fine_bbox.x_max, fine_bbox.y_max),
            region_state_snapshot=region_state_snapshot,
            working=working,
        )
        place_hills(
            fine_z,
            fine_terrain,
            l0_hydro,
            terrain_registry=terrain_with_hills(world),
            seed=world_seed(world),
            z_min=world_z_min(world),
            z_max=world_z_max(world),
        )

        heightmap = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=fine_bbox,
            surface_z=fine_z,
        )
        tile_sparse_hydro = working.hydrology.fine_hydro_for_tile(GridX(tile_gx), GridY(tile_gy))
        tile_hydro = merge_hydro_hard_corridor(parent_light, tile_sparse_hydro)
        n_eff = run_gap_analysis(world, heightmap)
        return TileSurfaceState(
            heightmap=heightmap,
            n_eff=n_eff,
            hydrology=tile_hydro or None,
            surface_terrain=fine_terrain,
            surface_facing=fine_facing or None,
            surface_grade_uid=None,
            surface_region_uid=fine_region_uid or None,
        )

    async def generate_chunk_cells(
        self,
        world: World,
        locations: list[NamedLocation],
        bundle: SurfacePlanBundle,
        tile_gx: int,
        tile_gy: int,
        rect: ColumnRect,
        *,
        surface_state: TileSurfaceState | None = None,
        parent_light: ParentLightTile | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry] | None = None,
        working: SurfaceWorkingMaps,
    ) -> list[MapCell]:
        return self.generate_chunk_cells_sync(
            world, locations, bundle, tile_gx, tile_gy, rect,
            surface_state=surface_state,
            parent_light=parent_light,
            region_state_snapshot=region_state_snapshot,
            working=working,
        )

    def generate_chunk_cells_sync(
        self,
        world: World,
        locations: list[NamedLocation],
        bundle: SurfacePlanBundle,
        tile_gx: int,
        tile_gy: int,
        rect: ColumnRect,
        *,
        surface_state: TileSurfaceState | None = None,
        parent_light: ParentLightTile | None = None,
        region_state_snapshot: Mapping[str, StateSnapshotEntry] | None = None,
        working: SurfaceWorkingMaps,
    ) -> list[MapCell]:
        if surface_state is None:
            if parent_light is None or region_state_snapshot is None:
                raise ValueError(
                    "parent_light and region_state_snapshot required for L2 generate (WP-PERF-22)",
                )
            surface_state = self.build_tile_surface_state(
                world, locations, bundle, tile_gx, tile_gy, parent_light=parent_light,
                region_state_snapshot=region_state_snapshot,
                working=working,
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
