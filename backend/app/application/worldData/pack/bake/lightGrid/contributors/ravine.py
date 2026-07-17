"""Ravine contributor — local depression (tz_map_light_bake)."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain_masks
from app.application.worldData.pack.bake.lightGrid.paintTerrain import paint_system_terrain_cell
from app.application.worldData.masks.terrainMerge import PRESERVE_HYDROLOGY_ROLES
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.masks.enums.maskDomainId import LightContributorId

logger = logging.getLogger(__name__)

_NEIGHBORS_8: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


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
        painted = 0
        for gx, gy in ctx.tiles:
            for tx, ty, cell in compose.iter_tile(gx, gy):
                if cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
                    continue
                neighbor_zs: list[int] = []
                for dx, dy in _NEIGHBORS_8:
                    lx = gx * scale.side + tx + dx
                    ly = gy * scale.side + ty + dy
                    ngx = lx // scale.side
                    ngy = ly // scale.side
                    ntx = lx % scale.side
                    nty = ly % scale.side
                    if (ngx, ngy) not in tile_set:
                        continue
                    neighbor = compose.get(ngx, ngy, ntx, nty)
                    if neighbor is None:
                        continue
                    neighbor_zs.append(neighbor.surface_z)
                if len(neighbor_zs) < policy.min_neighbors:
                    continue
                if cell.surface_z <= min(neighbor_zs) - policy.min_drop:
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
        logger.debug(
            "light_contributor_ravine | world=%s painted=%d",
            ctx.world.world_uid,
            painted,
        )
