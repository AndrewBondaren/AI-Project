"""Shared helpers for pack map coordinate math."""

from __future__ import annotations

import math

from app.db.models.world import World


def world_tile_size_m(world: World) -> int:
    return world.map_cell_size_m


def tile_index(coord: int, tile_size: int) -> tuple[int, int]:
    gx = math.floor(coord / tile_size)
    local = coord - gx * tile_size
    return gx, local


def world_map_sample_index(local: int, tile_size: int, cells_per_side: int) -> int:
    if tile_size <= 0 or cells_per_side <= 0:
        return 0
    return min(cells_per_side - 1, max(0, local * cells_per_side // tile_size))
