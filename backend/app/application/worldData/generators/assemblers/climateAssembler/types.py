from dataclasses import dataclass
from typing import Literal

from app.application.worldData.generators.coordinates.types import SurfaceGridRect


@dataclass(frozen=True)
class RecalcTrigger:
    """Hook for future DAG recalculate_climate node — pure data, no engine import."""

    kind: Literal["anchor_changed", "zone_changed", "terrain_changed", "manual"]
    bbox: SurfaceGridRect | None = None
    location_uids: frozenset[str] = frozenset()
