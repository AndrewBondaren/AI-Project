"""``system_terrain`` merge rank — tz_map_light_bake § Surface mask domains."""

from __future__ import annotations

from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole

PRESERVE_HYDROLOGY_ROLES: frozenset[WorldMapHydrologyRole] = frozenset(
    {
        WorldMapHydrologyRole.SEA,
        WorldMapHydrologyRole.LAKE,
        WorldMapHydrologyRole.RIVER,
    }
)


def terrain_merge_rank(system_terrain: str | None, masks: WorldTerrainMasks) -> int:
    """Higher rank wins. Unknown / None → 0 (always overwritable by known masks)."""
    if not system_terrain:
        return 0
    order = masks.merge_rank_order()
    try:
        # road index 0 → highest rank
        return len(order) - order.index(system_terrain)
    except ValueError:
        return 0


def may_paint_terrain(
    current: str | None,
    new_key: str,
    masks: WorldTerrainMasks,
) -> bool:
    return terrain_merge_rank(new_key, masks) >= terrain_merge_rank(current, masks)
