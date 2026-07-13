"""WP-15 loading progress snapshots — percent axes tiles / locations / wilderness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LoadingPhase = Literal["tiles", "locations", "wilderness", "idle"]


def progress_pct(ready: int, total: int) -> float:
    """0…100. Empty work (total=0) → 100."""
    if total <= 0:
        return 100.0
    return round(100.0 * min(ready, total) / total, 1)


@dataclass
class WorldMapLoading:
    phase: LoadingPhase = "idle"
    tiles_pct: float = 0.0
    locations_pct: float = 0.0
    wilderness_pct: float = 0.0
    tiles_ready: int = 0
    tiles_total: int = 0
    locations_ready: int = 0
    locations_total: int = 0
    wilderness_ready: int = 0
    wilderness_total: int = 0


@dataclass
class LocalGridLoading:
    phase: LoadingPhase = "idle"
    refine_pct: float = 0.0
    anchor_x: int | None = None
    anchor_y: int | None = None
    chunks_ready: int = 0
    chunks_total: int = 0
    tile_gx: int | None = None
    tile_gy: int | None = None
    climate_status: Literal["coarse_only", "fine_ready"] | None = None


@dataclass
class LoadingProgressSnapshot:
    world_uid: str
    world_map: WorldMapLoading = field(default_factory=WorldMapLoading)
    local_grid: LocalGridLoading = field(default_factory=LocalGridLoading)
    has_climate_coarse: bool = False

    def to_dict(self) -> dict:
        return {
            "world_uid": self.world_uid,
            "has_climate_coarse": self.has_climate_coarse,
            "worldMapLoading": {
                "phase": self.world_map.phase,
                "tiles_pct": self.world_map.tiles_pct,
                "locations_pct": self.world_map.locations_pct,
                "wilderness_pct": self.world_map.wilderness_pct,
                "tiles_ready": self.world_map.tiles_ready,
                "tiles_total": self.world_map.tiles_total,
                "locations_ready": self.world_map.locations_ready,
                "locations_total": self.world_map.locations_total,
                "wilderness_ready": self.world_map.wilderness_ready,
                "wilderness_total": self.world_map.wilderness_total,
            },
            "localGridLoading": {
                "phase": self.local_grid.phase,
                "refine_pct": self.local_grid.refine_pct,
                "anchor_x": self.local_grid.anchor_x,
                "anchor_y": self.local_grid.anchor_y,
                "chunks_ready": self.local_grid.chunks_ready,
                "chunks_total": self.local_grid.chunks_total,
                "tile_gx": self.local_grid.tile_gx,
                "tile_gy": self.local_grid.tile_gy,
                "climate_status": self.local_grid.climate_status,
            },
        }
