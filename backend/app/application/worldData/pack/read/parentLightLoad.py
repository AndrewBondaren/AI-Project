"""load_parent_light — disk SoT + process cache (tz_world_pack_storage Parent light SoT)."""

from __future__ import annotations

import logging

from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.read.parentLightCache import ParentLightCache
from app.dataModel.worldPack.parentLightTile import ParentLightTile

logger = logging.getLogger(__name__)


class MissingParentLightError(LookupError):
    """L0 parent light required for L2 refine but missing on disk/cache."""

    def __init__(self, world_uid: str, gx: int, gy: int) -> None:
        self.world_uid = world_uid
        self.gx = gx
        self.gy = gy
        super().__init__(
            f"parent light missing for world={world_uid} tile=({gx},{gy}); bake L0 first",
        )


def load_parent_light(
    world_uid: str,
    gx: int,
    gy: int,
    *,
    reader: WorldPackReader,
    cache: ParentLightCache,
    tile_m: int,
) -> ParentLightTile | None:
    """Return baked L0 tile view. Cache hit or decode ``world_map.zst`` → put."""
    hit = cache.get(world_uid, gx, gy)
    if hit is not None:
        return hit
    try:
        side, cells = reader.read_world_map_tile(gx, gy)
    except FileNotFoundError:
        logger.error(
            "parent_light_missing | world=%s gx=%d gy=%d — no world_map.zst",
            world_uid,
            gx,
            gy,
        )
        return None
    except (OSError, ValueError) as exc:
        logger.error(
            "parent_light_read_failed | world=%s gx=%d gy=%d err=%s",
            world_uid,
            gx,
            gy,
            exc,
        )
        return None
    tile = ParentLightTile.from_cells(
        world_uid=world_uid,
        gx=gx,
        gy=gy,
        side=side,
        tile_m=tile_m,
        cells=cells,
    )
    cache.put(tile)
    return tile


def require_parent_light(
    world_uid: str,
    gx: int,
    gy: int,
    *,
    reader: WorldPackReader,
    cache: ParentLightCache,
    tile_m: int,
) -> ParentLightTile:
    """Fail-closed load — raises ``MissingParentLightError`` when L0 is absent."""
    tile = load_parent_light(
        world_uid, gx, gy, reader=reader, cache=cache, tile_m=tile_m,
    )
    if tile is None:
        raise MissingParentLightError(world_uid, gx, gy)
    return tile
