"""L0 fine-tile policy → which macro-tiles get denser climate (WP-18 / bake modes)."""

from __future__ import annotations

import logging

from app.application.worldData.pack.read.packMapHelpers import tile_for_anchor
from app.dataModel.worldPack.lightFineTilePolicy import LightFineTilePolicy
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def resolve_fine_tiles_for_policy(
    policy: LightFineTilePolicy,
    tiles: list[tuple[int, int]],
    world: World,
    locations: list[NamedLocation],
    *,
    anchor_x: int | None,
    anchor_y: int | None,
) -> list[tuple[int, int]]:
    """Return fine climate tiles. ``spawn_player`` only if spawn tile ∈ planned L0 set."""
    if policy == "none" or not tiles:
        return []
    if policy == "all_baked_tiles":
        return list(tiles)
    # spawn_player
    ax, ay = anchor_x, anchor_y
    if ax is None or ay is None:
        for loc in locations:
            if loc.map_x is not None and loc.map_y is not None:
                ax, ay = loc.map_x, loc.map_y
                break
    if ax is None or ay is None:
        logger.warning(
            "light_fine_policy spawn_player | world=%s no spawn anchor; skip fine",
            world.world_uid,
        )
        return []
    spawn = tile_for_anchor(world, ax, ay)
    planned = set(tiles)
    if spawn not in planned:
        logger.warning(
            "light_fine_policy spawn_player | world=%s spawn_tile=%s not in planned L0; skip fine",
            world.world_uid,
            spawn,
        )
        return []
    return [spawn]
