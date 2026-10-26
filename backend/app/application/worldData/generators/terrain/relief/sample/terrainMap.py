"""Map system_terrain → ReliefConditionTerrain (R34); skip unknown."""

from __future__ import annotations

from app.dataModel.terrain.relief.enums import ReliefConditionTerrain
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

_MAP: dict[str, ReliefConditionTerrain] = {e.value: e for e in ReliefConditionTerrain}


def map_system_terrain(
    system_terrain: str | None,
    terrain_registry: WorldTerrainRegistry | None = None,
) -> ReliefConditionTerrain | None:
    """Return condition key or None → skip grade-site (R34)."""
    if not system_terrain:
        return None
    if terrain_registry is not None:
        entry = terrain_registry.entry_for(system_terrain)
        if entry is not None and entry.supports_open_land_grade:
            return ReliefConditionTerrain(entry.open_land_profile)
    return _MAP.get(system_terrain)
