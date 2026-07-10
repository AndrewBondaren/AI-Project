"""WP-15 loading progress snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LoadingPhase = Literal["idle", "blocking", "background"]


@dataclass
class WorldMapLoading:
    phase: LoadingPhase = "idle"
    world_map_tiles_ready: int = 0
    world_map_tiles_total: int = 0
    locations_ready: list[str] = field(default_factory=list)
    location_terrain_ready: list[str] = field(default_factory=list)


@dataclass
class LocalGridLoading:
    phase: LoadingPhase = "idle"
    anchor_x: int | None = None
    anchor_y: int | None = None
    chunks_ready: int = 0
    chunks_total: int = 0
    tile_gx: int | None = None
    tile_gy: int | None = None


@dataclass
class LoadingProgressSnapshot:
    world_uid: str
    world_map: WorldMapLoading = field(default_factory=WorldMapLoading)
    local_grid: LocalGridLoading = field(default_factory=LocalGridLoading)

    def to_dict(self) -> dict:
        return {
            "world_uid": self.world_uid,
            "worldMapLoading": {
                "phase": self.world_map.phase,
                "world_map_tiles_ready": self.world_map.world_map_tiles_ready,
                "world_map_tiles_total": self.world_map.world_map_tiles_total,
                "locations_ready": list(self.world_map.locations_ready),
                "location_terrain_ready": list(self.world_map.location_terrain_ready),
            },
            "localGridLoading": {
                "phase": self.local_grid.phase,
                "anchor_x": self.local_grid.anchor_x,
                "anchor_y": self.local_grid.anchor_y,
                "chunks_ready": self.local_grid.chunks_ready,
                "chunks_total": self.local_grid.chunks_total,
                "tile_gx": self.local_grid.tile_gx,
                "tile_gy": self.local_grid.tile_gy,
            },
        }
