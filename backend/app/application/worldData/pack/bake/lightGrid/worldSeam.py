"""AABB wrap seam on L0 light grid — ``full_bake`` only.

Lookup: ``WorldBounds.wrap_owner_and_other`` / ``facing_to_antagonist``.
Copy: ``WorldSeamCopy`` (surface_z + system_terrain). Not climate/hydro/grade.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.macroTileUid import macro_tile_uid
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing, opposite
from app.dataModel.worldPack.worldBounds import WorldBounds

logger = logging.getLogger(__name__)

_Tile = tuple[int, int]


def apply_world_seam(
    compose: LightGridCompose,
    bounds: WorldBounds,
    tiles: Iterable[_Tile],
    *,
    world_seed: str | None = None,
) -> int:
    """Stitch antagonist rims. Owner from ``WorldBounds.wrap_owner_and_other``.

    Skips a pair when either tile is not in ``tiles`` (partial light bake).
    """
    tile_set = set(tiles)
    seen: set[frozenset[_Tile]] = set()
    pairs = 0
    for gx, gy in tile_set:
        for facing in CARDINAL_FACINGS:
            pair = bounds.wrap_owner_and_other(gx, gy, facing)
            if pair is None:
                continue
            owner, other = pair
            if owner not in tile_set or other not in tile_set:
                continue
            key = frozenset((owner, other))
            if key in seen:
                continue
            seen.add(key)
            owner_facing = bounds.facing_to_antagonist(owner, other)
            if owner_facing is None:
                continue
            _copy_rim(compose, owner, other, owner_facing)
            pairs += 1
            if world_seed is not None:
                logger.info(
                    "world_seam | owner=%s antagonist=%s facing=%s",
                    macro_tile_uid(
                        world_seed=world_seed, tile_gx=owner[0], tile_gy=owner[1],
                    ),
                    macro_tile_uid(
                        world_seed=world_seed, tile_gx=other[0], tile_gy=other[1],
                    ),
                    owner_facing.value,
                )
    return pairs


def _copy_rim(
    compose: LightGridCompose,
    owner: _Tile,
    other: _Tile,
    owner_facing: Facing,
) -> None:
    scale = compose.scale
    owner_rim = scale.rim_tx_ty(owner_facing)
    other_rim = scale.rim_tx_ty(opposite(owner_facing))
    ogx, ogy = owner
    agx, agy = other
    for (otx, oty), (atx, aty) in zip(owner_rim, other_rim, strict=True):
        src = compose.ensure(ogx, ogy, otx, oty)
        dst = compose.ensure(agx, agy, atx, aty)
        dst.apply_seam_copy(src.seam_copy())
