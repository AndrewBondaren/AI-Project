"""Ravine contributor — local depression (tz_map_light_bake)."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.reliefObjects import resolve_ravine_surface_z
from app.application.worldData.generators.terrain.reliefObjects.depressionDetect import (
    NEIGHBORS_8,
    detect_depression_cells,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.application.worldData.pack.bake.lightGrid.paintTerrain import paint_system_terrain_cell
from app.application.worldData.masks.terrainMerge import PRESERVE_HYDROLOGY_ROLES
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.masks.enums.maskDomainId import LightContributorId

logger = logging.getLogger(__name__)


class RavineContributor:
    name = LightContributorId.RAVINE.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        masks = terrain_masks(ctx.world)
        policy = masks.default_ravines
        if not masks.category_enabled(policy):
            logger.debug(
                "light_contributor_ravine | world=%s skipped=disabled",
                ctx.world.world_uid,
            )
            return
        if not policy.autoresolve:
            return

        scale = compose.scale
        tile_set = set(ctx.tiles)
        z_min = world_z_min(ctx.world)

        # Flatten light cells in tile set to a z map keyed by absolute light coords.
        surface_z: dict[tuple[int, int], int] = {}
        key_to_tile: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for gx, gy in ctx.tiles:
            for tx, ty, cell in compose.iter_tile(gx, gy):
                if cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
                    continue
                lx = gx * scale.side + tx
                ly = gy * scale.side + ty
                surface_z[(lx, ly)] = cell.surface_z
                key_to_tile[(lx, ly)] = (gx, gy, tx, ty)

        def _neighbor_z(key: tuple[int, int]) -> list[int]:
            lx, ly = key
            out: list[int] = []
            for dx, dy in NEIGHBORS_8:
                n = (lx + dx, ly + dy)
                ngx = n[0] // scale.side
                ngy = n[1] // scale.side
                if (ngx, ngy) not in tile_set:
                    continue
                if n in surface_z:
                    out.append(surface_z[n])
                    continue
                ntx = n[0] % scale.side
                nty = n[1] % scale.side
                neighbor = compose.get(ngx, ngy, ntx, nty)
                if neighbor is not None:
                    out.append(neighbor.surface_z)
            return out

        painted = 0
        for key in detect_depression_cells(
            surface_z, policy, neighbor_z=_neighbor_z,
        ):
            gx, gy, tx, ty = key_to_tile[key]
            cell = compose.get(gx, gy, tx, ty)
            if cell is None:
                continue
            if paint_system_terrain_cell(
                compose,
                gx,
                gy,
                tx,
                ty,
                policy.system_terrain,
                masks=masks,
                preserve_hydro=True,
            ):
                painted += 1
                cell.surface_z = resolve_ravine_surface_z(
                    cell.surface_z,
                    z_min=z_min,
                    policy=policy,
                )
        logger.debug(
            "light_contributor_ravine | world=%s painted=%d",
            ctx.world.world_uid,
            painted,
        )
