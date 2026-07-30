"""Map system_terrain → ReliefConditionTerrain (R34); skip unknown."""

from __future__ import annotations

from app.dataModel.terrain.relief.enums import ReliefConditionTerrain

_MAP: dict[str, ReliefConditionTerrain] = {e.value: e for e in ReliefConditionTerrain}


def map_system_terrain(system_terrain: str | None) -> ReliefConditionTerrain | None:
    """Return condition key or None → skip grade-site (R34)."""
    if not system_terrain:
        return None
    return _MAP.get(system_terrain)
