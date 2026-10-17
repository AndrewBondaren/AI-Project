"""``system_terrain`` merge rank — tz_map_light_bake § Surface mask domains."""

from __future__ import annotations

from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole

PRESERVE_HYDROLOGY_ROLES: frozenset[WorldMapHydrologyRole] = frozenset(
    {
        WorldMapHydrologyRole.SEA,
        WorldMapHydrologyRole.LAKE,
        WorldMapHydrologyRole.RIVER,
    }
)


def terrain_merge_rank(system_terrain: str, registry: WorldTerrainRegistry) -> int:
    """World entry wins; an absent builtin may use its canonical engine entry.

    A missing custom key is a contract error, never an invented rank.
    """
    entry = registry.entry_for(system_terrain)
    if entry is None:
        entry = WorldTerrainRegistry.canonical_engine().entry_for(system_terrain)
    if entry is None:
        raise ValueError(f"terrain registry has no entry for {system_terrain!r}")
    return entry.merge_rank


def may_paint_terrain(
    current: str | None,
    new_key: str,
    registry: WorldTerrainRegistry,
) -> bool:
    new_rank = terrain_merge_rank(new_key, registry)
    return current is None or new_rank >= terrain_merge_rank(current, registry)
